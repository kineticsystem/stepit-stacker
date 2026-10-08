"""Tests how the pipeline runs StepIt Holo to show a quilt: the interleaving itself is tested in modules/stepit-holo."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import display
from pipeline.config import Quilt

QUILT = Quilt(columns=8, rows=6, view_width=420, view_height=560, reverse=False)


def fake_stepit_holo(folder, main):
    """A stand-in for StepIt Holo whose `python3 -m stepit_holo` runs `main`."""
    package = Path(folder, "stepit_holo")
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "__main__.py").write_text(main)
    return Path(folder)


class DisplayTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(mock.patch.dict(os.environ, {"DISPLAY": ":0"}))
        self.addCleanup(display.stop_viewer)

    def test_runs_stepit_holo_show_with_the_quilts_layout(self):
        with tempfile.TemporaryDirectory() as folder:
            holo = fake_stepit_holo(folder, "import sys, time\n"
                                            "print('Showing', ' '.join(sys.argv[1:]), flush=True)\n"
                                            "time.sleep(30)\n")
            display.show(Path(folder, "s_qs8x6a0.75.png"), QUILT, holo)
            output = display.VIEWER_LOG.read_text()
            self.assertIn("show", output)
            self.assertIn("--columns 8 --rows 6", output)

    def test_says_why_stepit_holo_stopped(self):
        with tempfile.TemporaryDirectory() as folder:
            holo = fake_stepit_holo(folder, "import sys\n"
                                            "print('stepit-holo: no Looking Glass found', flush=True)\n"
                                            "sys.exit(1)\n")
            with self.assertRaisesRegex(RuntimeError, "no Looking Glass found"):
                display.show(Path(folder, "s_qs8x6a0.75.png"), QUILT, holo)

    def test_says_when_the_submodule_is_missing(self):
        with tempfile.TemporaryDirectory() as folder, self.assertRaisesRegex(RuntimeError, "submodule update"):
            display.show(Path(folder, "s.png"), QUILT, Path(folder, "missing"))

    def test_needs_a_desktop(self):
        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(RuntimeError, "no desktop"):
            display.show(Path("s.png"), QUILT)


if __name__ == "__main__":
    unittest.main()
