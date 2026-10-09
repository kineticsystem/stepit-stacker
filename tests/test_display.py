"""Tests how the pipeline uploads a quilt to StepIt Holo's server, against a stand-in for it."""

import email.parser
import email.policy
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pipeline import display
from pipeline.config import Quilt

QUILT = Quilt(columns=8, rows=6, view_width=420, view_height=560, reverse=True)


class FakeHolo(BaseHTTPRequestHandler):
    """Answers POST /quilt with the server's status and body, and keeps the form it was sent."""

    status, answer, received = 200, {"shown_on": "HDMI-A-1 of /dev/dri/card1, 1536 x 2048"}, None

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        message = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
            f"Content-Type: {self.headers['Content-Type']}\r\n\r\n".encode() + body)
        FakeHolo.received = (self.path, {part.get_param("name", header="content-disposition"):
                                         (part.get_filename(), part.get_content()) for part in message.iter_parts()})
        data = json.dumps(self.answer).encode()
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_):
        pass


class DisplayTest(unittest.TestCase):
    def setUp(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeHolo)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.url = f"http://127.0.0.1:{server.server_address[1]}"
        self.quilt = Path(self.enterContext(tempfile.TemporaryDirectory()), "s_qs8x6a0.75.png")
        self.quilt.write_bytes(b"\x89PNG the quilt")
        FakeHolo.status, FakeHolo.received = 200, None
        FakeHolo.answer = {"shown_on": "HDMI-A-1 of /dev/dri/card1, 1536 x 2048"}

    def test_uploads_the_quilt_with_its_layout(self):
        with self.assertLogs("pipeline.display") as logs:
            display.show(self.quilt, QUILT, self.url + "/")
        path, fields = FakeHolo.received
        self.assertEqual(path, "/quilt")
        self.assertEqual(fields["file"], ("s_qs8x6a0.75.png", b"\x89PNG the quilt"))
        self.assertEqual((fields["columns"][1], fields["rows"][1]), ("8", "6"))
        # The quilt is in the order of its views already: the server must not turn it round.
        self.assertEqual(fields["reverse"][1], "false")
        self.assertIn("HDMI-A-1", logs.output[0])

    def test_a_quilt_kept_for_later_is_not_an_error(self):
        FakeHolo.status, FakeHolo.answer = 503, {"detail": "no Looking Glass found."}
        with self.assertLogs("pipeline.display", "WARNING") as logs:
            display.show(self.quilt, QUILT, self.url)
        self.assertIn("no Looking Glass found", logs.output[0])

    def test_says_why_the_server_refused_it(self):
        FakeHolo.status, FakeHolo.answer = 400, {"detail": "cannot read the quilt"}
        with self.assertRaisesRegex(RuntimeError, "refused s_qs8x6a0.75.png: cannot read the quilt"):
            display.show(self.quilt, QUILT, self.url)

    def test_says_when_the_server_cannot_be_reached(self):
        with self.assertRaisesRegex(RuntimeError, "cannot reach StepIt Holo at http://127.0.0.1:9"):
            display.show(self.quilt, QUILT, "http://127.0.0.1:9")

    def test_needs_a_url(self):
        with self.assertRaisesRegex(RuntimeError, "no display.url"):
            display.show(self.quilt, QUILT, "")


if __name__ == "__main__":
    unittest.main()
