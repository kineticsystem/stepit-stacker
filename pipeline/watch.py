"""The watcher: processes each angle as soon as the rig has shot it, and shows the session when it is complete.

For each angle the rig announces, it copies the angle into the mirror and
processes it, then, with display.progress, shows the quilt of the session's
angles graded so far, unless more of them wait in the queue. When the rig
announces that every angle of a session is done, it copies the session's
all_stacks.json, processes any angle it lists that has no graded image here
yet, then builds the quilt and shows it.

At every connection it also catches up: it processes every angle of the rig
that has a stack.json and no graded image here yet, e.g. angles shot while
this computer was off, then builds the quilt of every session that has an
all_stacks.json and no quilt here yet, without showing it. It catches up again
every minute, for an announcement that was lost, and shows a session it finds
then: it was finished while the watcher ran. Angles and sessions are processed
one at a time, in the order they come.
"""

import logging
import queue
import threading
import time

from .layout import Session
from .process import finish_session, preview_session, process_angle
from .rig import Rig, valid_folder

log = logging.getLogger(__name__)

ANGLE = "angle"
SESSION = "session"
CATCH_UP_EVERY = 60  # Seconds.


class Watcher:
    def __init__(self, config):
        self.config = config
        self.rig = Rig(config)
        self.queue = queue.Queue()
        # What waits in the queue, (kind, folder), with whether to show it: a
        # session queued by the catch-up is shown if the rig announces it too,
        # and an angle the rig announces shows a preview of its session.
        self.queued = {}
        # The angles and sessions that failed since the last connection: catching up every minute
        # leaves them alone, rather than merge an angle that cannot be aligned again and again.
        self.failed = set()
        self.reachable = True
        # What the worker processes now, (kind, folder): not queued again meanwhile, e.g. by the catch-up, which
        # finds the angle without its graded image yet.
        self.current = None
        self.lock = threading.Lock()

    def enqueue(self, kind, folder, reason, show=False):
        # A session is one folder of the rig's pictures folder, an angle one folder in a session.
        if not valid_folder(folder) or folder.count("/") != (1 if kind == ANGLE else 0):
            log.warning("Ignoring a %s with an unexpected name: %r", kind, folder)
            return
        key = (kind, folder)
        with self.lock:
            if key == self.current and kind == ANGLE:
                return
            if key in self.queued:
                self.queued[key] = self.queued[key] or show
                return
            self.queued[key] = show
        log.info("Queued the %s %s (%s)", kind, folder, reason)
        self.queue.put(key)

    def catch_up(self, periodic=False):
        """Queues the rig's finished angles and sessions that have no image or quilt here.

        At a connection, it retries what failed, and does not show the sessions: they are old, and
        shown one after the other, the oldest would end up on the Portrait. Every minute after, it
        leaves what failed alone, shows the sessions, finished while the watcher ran, and logs only
        what it finds."""
        try:
            angles, sessions = self.rig.finished()
        except Exception as error:  # noqa: BLE001
            # Once, not every minute while the rig is off.
            if self.reachable or not periodic:
                log.error("Cannot list the finished stacks of the rig: %s", getattr(error, "stderr", "") or error)
            self.reachable = False
            return
        if not self.reachable:
            log.info("The rig answers again")
        self.reachable = True
        with self.lock:
            if not periodic:
                self.failed.clear()
            failed = set(self.failed)
        pending = [folder for folder in angles if not self.graded(folder) and (ANGLE, folder) not in failed]
        unfinished = [name for name in sessions if not self.quilted(name) and (SESSION, name) not in failed]
        if not periodic:
            log.info("The rig has %d finished angles, %d not processed here yet", len(angles), len(pending))
            log.info("The rig has %d finished sessions, %d without a quilt here yet", len(sessions), len(unfinished))
        reason = "found in the last minute" if periodic else "catching up"
        for folder in pending:
            self.enqueue(ANGLE, folder, reason)
        for name in unfinished:
            self.enqueue(SESSION, name, reason, show=periodic)

    def keep_catching_up(self):
        while True:
            time.sleep(CATCH_UP_EVERY)
            self.catch_up(periodic=True)

    def fail(self, kind, folder):
        log.exception("Processing %s failed", folder)
        with self.lock:
            self.failed.add((kind, folder))

    def session_and_angle(self, folder):
        """The session of an angle of the rig, relative to its pictures folder, and the angle's folder in the mirror."""
        name, angle = folder.split("/", 1)
        session = Session(self.config.mirror / name)
        return session, session.angle(angle)

    def graded(self, folder):
        session, angle = self.session_and_angle(folder)
        return session.graded(angle).exists()

    def quilted(self, name):
        return Session(self.config.mirror / name).quilt(self.config.quilt).exists()

    def on_connect(self):
        threading.Thread(target=self.catch_up, daemon=True).start()

    def on_stack_done(self, folder):
        self.enqueue(ANGLE, folder, "announced by the rig", show=True)

    def on_all_stacks_done(self, folder):
        self.enqueue(SESSION, folder, "announced by the rig", show=True)

    def angles_waiting(self, name, done):
        """Whether other angles of the session than `done` wait in the queue. The catch-up may have queued `done`
        again while it was processed: it is processed already, and does not count."""
        with self.lock:
            return any(kind == ANGLE and folder.startswith(f"{name}/") and folder != done
                       for kind, folder in self.queued)

    def handle_angle(self, folder, show=False):
        if self.rig.copy(folder) is None:
            return
        session, angle = self.session_and_angle(folder)
        if session.is_processed(angle):
            log.info("%s is processed already", folder)
            return
        process_angle(session, angle, self.config)
        # Only the latest preview matters: none while the queue catches up.
        if show and self.config.display_progress and not self.angles_waiting(session.name, folder):
            preview_session(session, self.config)

    def handle_session(self, name, show):
        description = self.rig.copy_all_stacks(name)
        # An angle whose announcement was missed, e.g. lost with the connection.
        for stack in description.get("stacks", []):
            folder = f"{name}/{stack}"
            if not valid_folder(folder):
                log.warning("Ignoring an angle with an unexpected name: %r", folder)
            elif not self.graded(folder):
                try:
                    self.handle_angle(folder)
                except Exception:  # noqa: BLE001 - one bad angle must not stop the others
                    self.fail(ANGLE, folder)
        log.info("%s is complete", name)
        finish_session(Session(self.config.mirror / name), self.config, show)

    def work(self):
        while True:
            key = self.queue.get()
            kind, folder = key
            # Out of the queue before it runs: an announcement that comes
            # meanwhile queues it again, e.g. to show a session.
            with self.lock:
                show = self.queued.pop(key)
                self.current = key
            try:
                if kind == SESSION:
                    self.handle_session(folder, show)
                else:
                    self.handle_angle(folder, show)
            except Exception:  # noqa: BLE001 - one bad angle or session must not stop the others
                self.fail(kind, folder)
            finally:
                with self.lock:
                    self.current = None

    def run(self):
        threading.Thread(target=self.work, daemon=True).start()
        threading.Thread(target=self.keep_catching_up, daemon=True).start()
        self.rig.listen(self.on_connect, self.on_stack_done, self.on_all_stacks_done)
