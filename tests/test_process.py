"""Tests the preview of a session while the rig shoots, with real quilts and a stand-in for the display."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cv2
import numpy as np

from pipeline import process
from pipeline.config import Config, Quilt
from pipeline.layout import Session

QUILT = Quilt(columns=8, rows=6, view_width=42, view_height=56, reverse=False)
ANGLES = ["angle_01_-1.0deg", "angle_02_0.0deg", "angle_03_1.0deg"]


class PreviewTest(unittest.TestCase):
    def setUp(self):
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.config = Config(rig_host="rig", rig_port=9090, rig_pictures_port=8090, mirror=folder, rotate=0,
                             quilt=QUILT, display_url="http://holo:8095", display_progress=True)
        self.session = Session(folder / "2026-10-09_10-00-00")
        self.shown = []
        self.enterContext(mock.patch.object(process.display, "show",
                                            side_effect=lambda path, *_: self.shown.append(path.name)))

    def shoot_and_grade(self, count):
        """The first `count` angles, each with a raw frame and a graded image of its own grey."""
        for i, name in enumerate(ANGLES[:count]):
            angle = self.session.angle(name)
            angle.mkdir(parents=True, exist_ok=True)
            (angle / "IMG_0001.CR2").write_bytes(b"raw")
            graded = self.session.graded(angle)
            graded.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(graded), np.full((80, 60, 3), 20000 * (i + 1), np.uint16))

    def test_one_angle_has_no_depth_and_no_preview(self):
        self.shoot_and_grade(1)
        self.assertIsNone(process.preview_session(self.session, self.config))
        self.assertEqual(self.shown, [])

    def test_shows_the_quilt_of_the_angles_done_so_far(self):
        self.shoot_and_grade(2)
        path = process.preview_session(self.session, self.config)
        self.assertEqual(path, self.session.preview(QUILT))
        self.assertEqual(self.shown, ["2026-10-09_10-00-00_preview_qs8x6a0.75.png"])
        self.assertEqual(cv2.imread(str(path)).shape, (6 * 56, 8 * 42, 3))
        # Not the session's quilt: the watcher takes that for a finished session.
        self.assertFalse(self.session.quilt(QUILT).exists())

    def test_the_sessions_quilt_replaces_the_preview(self):
        self.shoot_and_grade(2)
        process.preview_session(self.session, self.config)
        self.shoot_and_grade(3)
        process.finish_session(self.session, self.config)
        self.assertFalse(self.session.preview(QUILT).exists())
        self.assertEqual(self.shown[-1], "2026-10-09_10-00-00_qs8x6a0.75.png")
        # A finished session has no more previews.
        self.assertIsNone(process.preview_session(self.session, self.config))

    def test_a_display_that_fails_does_not_fail_the_angle(self):
        self.shoot_and_grade(2)
        with mock.patch.object(process.display, "show", side_effect=RuntimeError("cannot reach StepIt Holo")), \
                self.assertLogs("pipeline.process", "WARNING") as logs:
            self.assertIsNone(process.preview_session(self.session, self.config))
        self.assertIn("cannot reach StepIt Holo", logs.output[0])


if __name__ == "__main__":
    unittest.main()
