"""Tests how the pipeline reads the rig's pictures over HTTP, against a stand-in for StepIt Camera's web server."""

import json
import os
import tempfile
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pipeline.config import Config, Quilt
from pipeline.layout import STACK_FILE, mirrored
from pipeline.rig import Rig

SESSION = "2026-10-08_10-15-30"
ANGLE = f"{SESSION}/angle_01_-17.0deg"


class FakeCameraServer(ThreadingHTTPServer):
    """Serves a folder as StepIt Camera's web server does: /pictures/<path> a file, with Range, and
    /pictures/<folder>/ what the folder holds, as JSON, ?recursive=1 for everything below it."""

    def __init__(self, folder):
        self.folder = folder
        self.requests = []  # (path, Range header) of every request.
        super().__init__(("127.0.0.1", 0), Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        path = urllib.parse.unquote(url.path)
        self.server.requests.append((path, self.headers.get("Range")))
        if not path.startswith("/pictures/"):
            return self.send_error(404)
        target = self.server.folder / path[len("/pictures/"):]
        if path.endswith("/") and target.is_dir():
            recursive = "recursive=1" in url.query
            entries = sorted(target.rglob("*") if recursive else target.iterdir())
            body = json.dumps({
                "folder": path[len("/pictures/"):].rstrip("/"),
                "folders": [str(e.relative_to(target)) for e in entries if e.is_dir()],
                "files": [{"path": str(e.relative_to(target)), "size": e.stat().st_size, "modified": ""}
                          for e in entries if e.is_file()],
            }).encode()
            return self.reply(200, body, "application/json")
        if not target.is_file():
            return self.send_error(404)
        content = target.read_bytes()
        if self.headers.get("Range"):
            start = int(self.headers["Range"].split("=")[1].split("-")[0])
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(content) - 1}/{len(content)}")
            self.send_header("Content-Length", str(len(content) - start))
            self.end_headers()
            return self.wfile.write(content[start:])
        return self.reply(200, content, "application/octet-stream")

    def reply(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class RigTest(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.pictures = root / "rig"
        self.mirror = root / "mirror"
        self.server = FakeCameraServer(self.pictures)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        config = Config(rig_host="127.0.0.1", rig_port=9090, rig_pictures_port=self.server.server_address[1],
                        mirror=self.mirror, rotate=0,
                        quilt=Quilt(columns=8, rows=6, view_width=42, view_height=56, reverse=False))
        self.rig = Rig(config)

    def shoot(self, angle=ANGLE, frames=(b"frame one", b"frame two"), finished=True):
        folder = self.pictures / angle
        folder.mkdir(parents=True)
        names = []
        for i, content in enumerate(frames):
            names.append(f"IMG_{i + 1:04d}.CR2")
            (folder / names[-1]).write_bytes(content)
        if finished:
            (folder / "stack.json").write_text(json.dumps({"folder": angle, "files": names}))
        return names

    def local(self, name=""):
        return self.mirror / SESSION / "1_session" / ANGLE.split("/")[1] / name

    def fetched(self):
        return [path for path, _ in self.server.requests if path.endswith(".CR2")]

    def test_finds_the_finished_angles_and_sessions(self):
        self.shoot()
        self.shoot(f"{SESSION}/angle_02_-16.3deg", finished=False)
        (self.pictures / SESSION / "all_stacks.json").write_text("{}")
        self.assertEqual(self.rig.finished(), ([ANGLE], [SESSION]))

    def test_copies_an_angle_and_its_stack_json_last(self):
        names = self.shoot()
        description = self.rig.copy(ANGLE)
        self.assertEqual(description["files"], names)
        self.assertEqual(self.local("IMG_0001.CR2").read_bytes(), b"frame one")
        self.assertEqual(self.local("IMG_0002.CR2").read_bytes(), b"frame two")
        self.assertTrue(self.local("stack.json").exists())
        self.assertEqual(list(self.local().glob(".*")), [])  # No .part left.

    def test_skips_the_files_already_here(self):
        self.shoot()
        self.rig.copy(ANGLE)
        self.server.requests.clear()
        self.rig.copy(ANGLE)
        self.assertEqual(self.fetched(), [])

    def test_leaves_an_unchanged_stack_json_alone(self):
        # A newer stack.json than the graded image says that the angle must be processed again.
        self.shoot()
        self.rig.copy(ANGLE)
        stack = mirrored(self.mirror, ANGLE) / STACK_FILE
        os.utime(stack, (1, 1))
        self.rig.copy(ANGLE)
        self.assertEqual(stack.stat().st_mtime, 1)

    def test_continues_a_copy_cut_short(self):
        self.shoot(frames=(b"0123456789",))
        self.local().mkdir(parents=True)
        self.local(".IMG_0001.CR2.part").write_bytes(b"01234")
        self.rig.copy(ANGLE)
        self.assertEqual(self.local("IMG_0001.CR2").read_bytes(), b"0123456789")
        self.assertIn((f"/pictures/{ANGLE}/IMG_0001.CR2", "bytes=5-"), self.server.requests)

    def test_skips_an_angle_that_is_not_finished(self):
        self.shoot(finished=False)
        with self.assertLogs("pipeline.rig", "WARNING"):
            self.assertIsNone(self.rig.copy(ANGLE))
        self.assertEqual(self.fetched(), [])

    def test_refuses_an_angle_whose_files_are_not_all_there(self):
        self.shoot()
        (self.pictures / ANGLE / "IMG_0002.CR2").unlink()
        with self.assertLogs("pipeline.rig", "ERROR"):
            self.assertIsNone(self.rig.copy(ANGLE))
        self.assertFalse(self.local("stack.json").exists())

    def test_copies_the_all_stacks_json_of_a_session(self):
        (self.pictures / SESSION).mkdir(parents=True)
        (self.pictures / SESSION / "all_stacks.json").write_text(json.dumps({"stacks": ["angle_01_-17.0deg"]}))
        self.assertEqual(self.rig.copy_all_stacks(SESSION), {"stacks": ["angle_01_-17.0deg"]})
        self.assertTrue((self.mirror / SESSION / "1_session" / "all_stacks.json").exists())


if __name__ == "__main__":
    unittest.main()
