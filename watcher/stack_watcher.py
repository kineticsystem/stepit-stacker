#!/usr/bin/env python3
"""Merges each focus stack of the rig as soon as the rig has shot it.

The rig announces every finished stack, one angle of a FocusStack, on the
latched topic /focus_stack/stack_done, through the commander's rosbridge, and
writes stack.json into the stack's folder. This program follows that topic; for
each stack, it copies the folder into a mirror of the rig's pictures folder
with rsync, then merges it with the stacker, into <session>/stacked/<angle>.tif
next to it.

At every connection, it also catches up: it merges every stack of the rig that
has a stack.json and no image here yet, e.g. stacks shot while this computer
was off. Stacks are merged one at a time, in the order they come.
"""

import argparse
import json
import logging
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import websocket

TOPIC = "/focus_stack/stack_done"
STACK_FILE = "stack.json"
# A folder the rig announces, relative to its pictures folder, e.g.
# 2026-10-07_12-29-19/angle_01_0.0deg: names without spaces or "..", which the
# remote shell of rsync and ssh passes as they are.
FOLDER = re.compile(r"[A-Za-z0-9_+.-]+(/[A-Za-z0-9_+.-]+)*")

log = logging.getLogger("stepit-stacker-watcher")


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rig", default="stepit.local", help="the rig's host name (default: %(default)s)")
    parser.add_argument("--port", type=int, default=9090, help="the port of the commander's rosbridge")
    parser.add_argument("--user", default="robot", help="the user on the rig, for ssh and rsync")
    parser.add_argument(
        "--remote-pictures",
        default="stepit-macro/pictures",
        help="the rig's pictures folder, relative to the user's home on the rig (default: %(default)s)",
    )
    parser.add_argument("--mirror", required=True, type=Path, help="the mirror of the rig's pictures folder here")
    parser.add_argument("--stack", default="stack", help="the stacker command (default: %(default)s)")
    parser.add_argument("stack_options", nargs=argparse.REMAINDER, help="options for the stacker, after --")
    arguments = parser.parse_args()
    if arguments.stack_options[:1] == ["--"]:
        arguments.stack_options = arguments.stack_options[1:]
    return arguments


class Watcher:
    def __init__(self, arguments):
        self.arguments = arguments
        self.remote = f"{arguments.user}@{arguments.rig}"
        self.queue = queue.Queue()
        self.queued = set()
        self.lock = threading.Lock()

    # Which stacks to merge.

    def enqueue(self, folder, reason):
        if not FOLDER.fullmatch(folder) or ".." in folder.split("/"):
            log.warning("Ignoring a folder with an unexpected name: %r", folder)
            return
        with self.lock:
            if folder in self.queued:
                return
            self.queued.add(folder)
        log.info("Queued %s (%s)", folder, reason)
        self.queue.put(folder)

    def output(self, folder):
        """The image of a stack: <parent>/stacked/<name>.tif, in the mirror."""
        local = self.arguments.mirror / folder
        return local.parent / "stacked" / (local.name + ".tif")

    def is_merged(self, folder):
        """Whether the stack has an image newer than its stack.json, which a stack shot again would renew."""
        image = self.output(folder)
        stack_file = self.arguments.mirror / folder / STACK_FILE
        return image.exists() and stack_file.exists() and image.stat().st_mtime >= stack_file.stat().st_mtime

    def catch_up(self):
        """Queues every stack of the rig that has a stack.json and no image here yet."""
        try:
            result = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "BatchMode=yes",
                    self.remote,
                    f"find {self.arguments.remote_pictures} -mindepth 2 -name {STACK_FILE} -printf '%P\\n'",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            )
        except (subprocess.SubprocessError, OSError) as error:
            log.error("Cannot list the finished stacks of the rig: %s", getattr(error, "stderr", "") or error)
            return
        folders = sorted(str(Path(line).parent) for line in result.stdout.splitlines() if line.strip())
        pending = [folder for folder in folders if not self.is_merged(folder)]
        log.info("The rig has %d finished stacks, %d not merged here yet", len(folders), len(pending))
        for folder in pending:
            self.enqueue(folder, "catching up")

    # Merging.

    def work(self):
        while True:
            folder = self.queue.get()
            try:
                self.merge(folder)
            except Exception:  # noqa: BLE001 - one bad stack must not stop the others
                log.exception("Merging %s failed", folder)
            finally:
                with self.lock:
                    self.queued.discard(folder)

    def merge(self, folder):
        local = self.arguments.mirror / folder
        local.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        subprocess.run(
            [
                "rsync",
                "-a",
                "--partial",
                "-e",
                "ssh -o BatchMode=yes",
                f"{self.remote}:{self.arguments.remote_pictures}/{folder}/",
                f"{local}/",
            ],
            check=True,
            timeout=1800,
        )
        stack_file = local / STACK_FILE
        if not stack_file.exists():
            log.warning("%s has no %s on the rig: not finished, skipped", folder, STACK_FILE)
            return
        description = json.loads(stack_file.read_text())
        missing = [name for name in description.get("files", []) if not (local / name).exists()]
        if missing:
            log.error("%s: %d files of %s are missing after the copy, e.g. %s", folder, len(missing), STACK_FILE, missing[0])
            return
        log.info("Copied %s: %d files in %.0f s", folder, len(description.get("files", [])), time.monotonic() - started)

        if self.is_merged(folder):
            log.info("%s is merged already: %s", folder, self.output(folder))
            return
        # The stacker writes into a temporary folder, and the image is moved
        # into place once whole: a merge cut short leaves no image behind.
        image = self.output(folder)
        temporary = image.parent / f".{local.name}.tmp"
        shutil.rmtree(temporary, ignore_errors=True)
        temporary.mkdir(parents=True)
        try:
            started = time.monotonic()
            subprocess.run(
                [self.arguments.stack, str(local), "-o", str(temporary), *self.arguments.stack_options],
                check=True,
                timeout=3600,
            )
            os.replace(temporary / (local.name + ".tif"), image)
            log.info("Merged %s in %.0f s: %s", folder, time.monotonic() - started, image)
        finally:
            shutil.rmtree(temporary, ignore_errors=True)

    # Listening to the rig.

    def on_open(self, socket):
        log.info("Connected to the rig, ws://%s:%d", self.arguments.rig, self.arguments.port)
        socket.send(json.dumps({"op": "subscribe", "topic": TOPIC, "type": "std_msgs/msg/String"}))
        threading.Thread(target=self.catch_up, daemon=True).start()

    def on_message(self, _socket, text):
        message = json.loads(text)
        if message.get("op") == "publish" and message.get("topic") == TOPIC:
            self.enqueue(message["msg"]["data"], "announced by the rig")

    def on_error(self, _socket, error):
        log.warning("Connection to the rig: %s", error)

    def run(self):
        threading.Thread(target=self.work, daemon=True).start()
        url = f"ws://{self.arguments.rig}:{self.arguments.port}"
        while True:
            socket = websocket.WebSocketApp(url, on_open=self.on_open, on_message=self.on_message, on_error=self.on_error)
            # Pings find a rig that went away without closing the connection,
            # e.g. switched off.
            socket.run_forever(ping_interval=20, ping_timeout=10)
            log.info("Disconnected from the rig: connecting again in 10 s")
            time.sleep(10)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    Watcher(parse_arguments()).run()


if __name__ == "__main__":
    main()
