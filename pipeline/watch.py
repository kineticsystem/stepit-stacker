"""The watcher: processes each angle as soon as the rig has shot it, and shows the session when it is complete.

For each angle the rig announces, it copies the angle into the mirror and
processes it. When the rig has taken every picture of the session and no
angle of it waits any more, it builds the quilt and shows it.

At every connection it also catches up: it processes every angle of the rig
that has a stack.json and no graded image here yet, e.g. angles shot while
this computer was off. Angles are processed one at a time, in the order they
come.
"""

import logging
import queue
import threading

from .layout import Session
from .process import finish_session, process_angle
from .rig import Rig, valid_folder

log = logging.getLogger(__name__)


class Watcher:
    def __init__(self, config):
        self.config = config
        self.rig = Rig(config)
        self.queue = queue.Queue()
        self.queued = set()
        self.lock = threading.Lock()
        self.progress = None  # [pictures taken, pictures in total], from the rig.
        self.announced_session = None  # The session of the last angle the rig announced.

    def enqueue(self, folder, reason):
        if not valid_folder(folder):
            log.warning("Ignoring a folder with an unexpected name: %r", folder)
            return
        with self.lock:
            if folder in self.queued:
                return
            self.queued.add(folder)
        log.info("Queued %s (%s)", folder, reason)
        self.queue.put(folder)

    def catch_up(self):
        try:
            folders = self.rig.finished_stacks()
        except Exception as error:  # noqa: BLE001
            log.error("Cannot list the finished stacks of the rig: %s", getattr(error, "stderr", "") or error)
            return
        pending = []
        for folder in folders:
            angle = self.config.mirror / folder
            if not Session(angle.parent).graded(angle).exists():
                pending.append(folder)
        log.info("The rig has %d finished angles, %d not processed here yet", len(folders), len(pending))
        for folder in pending:
            self.enqueue(folder, "catching up")

    def on_connect(self):
        threading.Thread(target=self.catch_up, daemon=True).start()

    def on_stack_done(self, folder):
        self.announced_session = folder.split("/")[0]
        self.enqueue(folder, "announced by the rig")

    def on_progress(self, data):
        self.progress = data

    def session_complete(self, session, current):
        done, total = self.progress if self.progress and len(self.progress) == 2 else (0, -1)
        with self.lock:
            waiting = any(folder != current and folder.split("/")[0] == session.name for folder in self.queued)
        return session.name == self.announced_session and done == total and not waiting

    def handle(self, folder):
        if self.rig.copy(folder) is None:
            return
        angle = self.config.mirror / folder
        session = Session(angle.parent)
        if session.is_processed(angle):
            log.info("%s is processed already", folder)
        else:
            process_angle(session, angle, self.config)
        if self.session_complete(session, folder):
            log.info("%s is complete", session.name)
            finish_session(session, self.config)

    def work(self):
        while True:
            folder = self.queue.get()
            try:
                self.handle(folder)
            except Exception:  # noqa: BLE001 - one bad angle must not stop the others
                log.exception("Processing %s failed", folder)
            finally:
                with self.lock:
                    self.queued.discard(folder)

    def run(self):
        threading.Thread(target=self.work, daemon=True).start()
        self.rig.listen(self.on_connect, self.on_stack_done, self.on_progress)
