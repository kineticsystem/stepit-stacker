"""The rig: its announcements, through the commander's rosbridge, and its pictures, over HTTP.

The rig announces each finished stack, one angle of a FocusStack, on the
latched topic /focus_stack/stack_done, and writes stack.json into the angle's
folder. Once every angle is done, it announces the session's folder on the
latched topic /focus_stack/all_stacks_done, and writes all_stacks.json into it,
with the folders of its angles.

The pictures stay in the rig's pictures folder, which StepIt Camera's web
server serves, on port 8090: /pictures/<path> gives a file, and
/pictures/<folder>/ what a folder holds, as JSON, with the size of each file.
No key, and nothing is ever written to the rig.
"""

import json
import logging
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

import websocket

from .layout import ALL_STACKS_FILE, STACK_FILE, mirrored

log = logging.getLogger(__name__)

STACK_DONE = "/focus_stack/stack_done"
ALL_STACKS_DONE = "/focus_stack/all_stacks_done"
# An angle the rig announces, relative to its pictures folder, e.g.
# 2026-10-07_12-29-19/angle_01_0.0deg: names without spaces or "..", so that
# the path of a file here never leaves the mirror.
FOLDER = re.compile(r"[A-Za-z0-9_+.-]+(/[A-Za-z0-9_+.-]+)*")
# A file is read in pieces of this size: a RAW frame is about 25 MB.
CHUNK = 1 << 20
TIMEOUT = 60  # Seconds without an answer, for one request.


def valid_folder(folder):
    return bool(FOLDER.fullmatch(folder)) and ".." not in folder.split("/")


class Rig:
    def __init__(self, config):
        self.config = config
        self.pictures = f"http://{config.rig_host}:{config.rig_pictures_port}/pictures/"

    def url(self, path, folder=False):
        """The URL of a path of the rig's pictures folder; of the folder itself, for its listing, if `folder`."""
        quoted = "/".join(urllib.parse.quote(part) for part in Path(path).parts)
        return self.pictures + quoted + ("/" if folder and quoted else "")

    def get_json(self, url):
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
            return json.loads(response.read())

    def finished(self):
        """The angles of the rig that have a stack.json, and the sessions that have an all_stacks.json,
        relative to its pictures folder."""
        listing = self.get_json(self.pictures + "?recursive=1")
        paths = [Path(file["path"]) for file in listing["files"]]
        angles = sorted(str(path.parent) for path in paths if path.name == STACK_FILE and len(path.parts) == 3)
        sessions = sorted(str(path.parent) for path in paths if path.name == ALL_STACKS_FILE and len(path.parts) == 2)
        return angles, sessions

    def download(self, path, local, size):
        """Copies a file of the rig into `local`, unless it is there already, of the same size. It goes into a
        hidden .part file first, which a copy cut short continues, and takes its name once whole."""
        if local.exists() and local.stat().st_size == size:
            return
        part = local.with_name(f".{local.name}.part")
        done = part.stat().st_size if part.exists() else 0
        if done > size:
            part.unlink()
            done = 0
        request = urllib.request.Request(self.url(path))
        if done:
            request.add_header("Range", f"bytes={done}-")
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            # 206: the rest of the file; 200: the whole of it, from the start.
            mode = "ab" if done and response.status == 206 else "wb"
            with open(part, mode) as output:
                while chunk := response.read(CHUNK):
                    output.write(chunk)
        if part.stat().st_size != size:
            raise RuntimeError(f"{path}: {part.stat().st_size} bytes copied of {size}")
        part.replace(local)

    def copy(self, folder):
        """Copies an angle into the mirror, and returns its stack.json; None if it is not finished."""
        local = mirrored(self.config.mirror, folder)
        local.mkdir(parents=True, exist_ok=True)
        sizes = {file["path"]: file["size"] for file in self.get_json(self.url(folder, folder=True))["files"]}
        if STACK_FILE not in sizes:
            log.warning("%s has no %s on the rig: not finished, skipped", folder, STACK_FILE)
            return None
        with urllib.request.urlopen(self.url(f"{folder}/{STACK_FILE}"), timeout=TIMEOUT) as response:
            content = response.read()
        description = json.loads(content)
        names = description.get("files", [])
        missing = [name for name in names if name not in sizes]
        if missing:
            log.error("%s: %d files of %s are not on the rig, e.g. %s", folder, len(missing), STACK_FILE, missing[0])
            return None
        for name in names:
            if Path(name).name != name or name.startswith("."):
                raise RuntimeError(f"{folder}: {STACK_FILE} lists an unexpected file name: {name!r}")
            self.download(f"{folder}/{name}", local / name, sizes[name])
        # Written last: the angle here is complete once its stack.json is.
        (local / STACK_FILE).write_bytes(content)
        return description

    def copy_all_stacks(self, session):
        """Copies the all_stacks.json of a session into the mirror, and returns it."""
        local = mirrored(self.config.mirror, session)
        local.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(self.url(f"{session}/{ALL_STACKS_FILE}"), timeout=TIMEOUT) as response:
            content = response.read()
        (local / ALL_STACKS_FILE).write_bytes(content)
        return json.loads(content)

    def listen(self, on_connect, on_stack_done, on_all_stacks_done):
        """Follows the rig's topics forever, connecting again whenever the connection drops."""
        url = f"ws://{self.config.rig_host}:{self.config.rig_port}"

        def on_open(socket):
            log.info("Connected to the rig, %s", url)
            socket.send(json.dumps({"op": "subscribe", "topic": STACK_DONE, "type": "std_msgs/msg/String"}))
            socket.send(json.dumps({"op": "subscribe", "topic": ALL_STACKS_DONE, "type": "std_msgs/msg/String"}))
            on_connect()

        def on_message(_socket, text):
            message = json.loads(text)
            if message.get("op") != "publish":
                return
            if message.get("topic") == STACK_DONE:
                on_stack_done(message["msg"]["data"])
            elif message.get("topic") == ALL_STACKS_DONE:
                on_all_stacks_done(message["msg"]["data"])

        def on_error(_socket, error):
            log.warning("Connection to the rig: %s", error)

        while True:
            socket = websocket.WebSocketApp(url, on_open=on_open, on_message=on_message, on_error=on_error)
            # Pings find a rig that went away without closing the connection, e.g. switched off.
            socket.run_forever(ping_interval=20, ping_timeout=10)
            log.info("Disconnected from the rig: connecting again in 10 s")
            time.sleep(10)
