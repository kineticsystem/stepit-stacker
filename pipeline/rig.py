"""The rig: its announcements, through the commander's rosbridge, and its pictures, through ssh and rsync.

The rig announces each finished stack, one angle of a FocusStack, on the
latched topic /focus_stack/stack_done, and writes stack.json into the angle's
folder. It also publishes [pictures taken, pictures in total] for the whole
FocusStack on /focus_stack/progress: the session is complete when they are
equal.
"""

import json
import logging
import re
import subprocess
import time
from pathlib import Path

import websocket

from .layout import STACK_FILE

log = logging.getLogger(__name__)

STACK_DONE = "/focus_stack/stack_done"
PROGRESS = "/focus_stack/progress"
# An angle the rig announces, relative to its pictures folder, e.g.
# 2026-10-07_12-29-19/angle_01_0.0deg: names without spaces or "..", which the
# remote shell of rsync and ssh passes as they are.
FOLDER = re.compile(r"[A-Za-z0-9_+.-]+(/[A-Za-z0-9_+.-]+)*")


def valid_folder(folder):
    return bool(FOLDER.fullmatch(folder)) and ".." not in folder.split("/")


class Rig:
    def __init__(self, config):
        self.config = config
        self.remote = f"{config.rig_user}@{config.rig_host}"

    def finished_stacks(self):
        """Every angle of the rig that has a stack.json, relative to its pictures folder."""
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", self.remote,
             f"find {self.config.rig_pictures} -mindepth 2 -name {STACK_FILE} -printf '%P\\n'"],
            capture_output=True, text=True, timeout=60, check=True,
        )
        return sorted(str(Path(line).parent) for line in result.stdout.splitlines() if line.strip())

    def copy(self, folder):
        """Copies an angle into the mirror, and returns its stack.json; None if it is incomplete."""
        local = self.config.mirror / folder
        local.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["rsync", "-a", "--partial", "-e", "ssh -o BatchMode=yes",
             f"{self.remote}:{self.config.rig_pictures}/{folder}/", f"{local}/"],
            check=True, timeout=1800,
        )
        stack_file = local / STACK_FILE
        if not stack_file.exists():
            log.warning("%s has no %s on the rig: not finished, skipped", folder, STACK_FILE)
            return None
        description = json.loads(stack_file.read_text())
        missing = [name for name in description.get("files", []) if not (local / name).exists()]
        if missing:
            log.error("%s: %d files of %s are missing after the copy, e.g. %s", folder, len(missing), STACK_FILE,
                      missing[0])
            return None
        return description

    def listen(self, on_connect, on_stack_done, on_progress):
        """Follows the rig's topics forever, connecting again whenever the connection drops."""
        url = f"ws://{self.config.rig_host}:{self.config.rig_port}"

        def on_open(socket):
            log.info("Connected to the rig, %s", url)
            socket.send(json.dumps({"op": "subscribe", "topic": STACK_DONE, "type": "std_msgs/msg/String"}))
            socket.send(json.dumps({"op": "subscribe", "topic": PROGRESS, "type": "std_msgs/msg/Int32MultiArray"}))
            on_connect()

        def on_message(_socket, text):
            message = json.loads(text)
            if message.get("op") != "publish":
                return
            if message.get("topic") == STACK_DONE:
                on_stack_done(message["msg"]["data"])
            elif message.get("topic") == PROGRESS:
                on_progress(message["msg"]["data"])

        def on_error(_socket, error):
            log.warning("Connection to the rig: %s", error)

        while True:
            socket = websocket.WebSocketApp(url, on_open=on_open, on_message=on_message, on_error=on_error)
            # Pings find a rig that went away without closing the connection, e.g. switched off.
            socket.run_forever(ping_interval=20, ping_timeout=10)
            log.info("Disconnected from the rig: connecting again in 10 s")
            time.sleep(10)
