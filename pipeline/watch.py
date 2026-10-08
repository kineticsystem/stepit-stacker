"""The watcher: processes each angle as soon as the rig has shot it, and shows the session when it is complete.

For each angle the rig announces, it copies the angle into the mirror and
processes it. When the rig announces that every angle of a session is done, it
copies the session's all_stacks.json, processes any angle it lists that has no
graded image here yet, then builds the quilt and shows it.

At every connection it also catches up: it processes every angle of the rig
that has a stack.json and no graded image here yet, e.g. angles shot while
this computer was off, then builds the quilt of every session that has an
all_stacks.json and no quilt here yet, without showing it. Angles and sessions
are processed one at a time, in the order they come.
"""

import logging
import queue
import threading

from .layout import Session
from .process import finish_session, process_angle
from .rig import Rig, valid_folder

log = logging.getLogger(__name__)

ANGLE = "angle"
SESSION = "session"


class Watcher:
    def __init__(self, config):
        self.config = config
        self.rig = Rig(config)
        self.queue = queue.Queue()
        # What waits in the queue, (kind, folder), with whether to show it: a
        # session queued by the catch-up is shown if the rig announces it too.
        self.queued = {}
        self.lock = threading.Lock()

    def enqueue(self, kind, folder, reason, show=False):
        # A session is one folder of the rig's pictures folder, an angle one folder in a session.
        if not valid_folder(folder) or folder.count("/") != (1 if kind == ANGLE else 0):
            log.warning("Ignoring a %s with an unexpected name: %r", kind, folder)
            return
        key = (kind, folder)
        with self.lock:
            if key in self.queued:
                self.queued[key] = self.queued[key] or show
                return
            self.queued[key] = show
        log.info("Queued the %s %s (%s)", kind, folder, reason)
        self.queue.put(key)

    def catch_up(self):
        try:
            angles, sessions = self.rig.finished()
        except Exception as error:  # noqa: BLE001
            log.error("Cannot list the finished stacks of the rig: %s", getattr(error, "stderr", "") or error)
            return
        pending = [folder for folder in angles if not self.graded(folder)]
        log.info("The rig has %d finished angles, %d not processed here yet", len(angles), len(pending))
        for folder in pending:
            self.enqueue(ANGLE, folder, "catching up")
        unfinished = [name for name in sessions if not self.quilted(name)]
        log.info("The rig has %d finished sessions, %d without a quilt here yet", len(sessions), len(unfinished))
        for name in unfinished:
            self.enqueue(SESSION, name, "catching up")

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
        self.enqueue(ANGLE, folder, "announced by the rig")

    def on_all_stacks_done(self, folder):
        self.enqueue(SESSION, folder, "announced by the rig", show=True)

    def handle_angle(self, folder):
        if self.rig.copy(folder) is None:
            return
        session, angle = self.session_and_angle(folder)
        if session.is_processed(angle):
            log.info("%s is processed already", folder)
        else:
            process_angle(session, angle, self.config)

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
                    log.exception("Processing %s failed", folder)
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
            try:
                if kind == SESSION:
                    self.handle_session(folder, show)
                else:
                    self.handle_angle(folder)
            except Exception:  # noqa: BLE001 - one bad angle or session must not stop the others
                log.exception("Processing %s failed", folder)

    def run(self):
        threading.Thread(target=self.work, daemon=True).start()
        self.rig.listen(self.on_connect, self.on_stack_done, self.on_all_stacks_done)
