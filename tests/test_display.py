"""Tests the interleaving of a quilt for the Looking Glass Portrait, with the Portrait's calibration."""

import math
import unittest
from dataclasses import replace

import numpy as np

from pipeline.config import Quilt
from pipeline.display import Calibration, interleave

QUILT = Quilt(columns=8, rows=6, view_width=42, view_height=56, reverse=False)

# The calibration of a Looking Glass Portrait, LKG_calibration/visual.json on its drive.
VISUAL = {
    "configVersion": "1.0", "serial": "LKG-PORT-00671", "pitch": {"value": 52.58790040712976},
    "slope": {"value": -7.161397095759771}, "center": {"value": 0.7432299004945404}, "fringe": {"value": 0.0},
    "viewCone": {"value": 40.0}, "invView": {"value": 1.0}, "verticalAngle": {"value": 0.0},
    "DPI": {"value": 324.0}, "screenW": {"value": 1536.0}, "screenH": {"value": 2048.0},
    "flipImageX": {"value": 0.0}, "flipImageY": {"value": 0.0}, "flipSubp": {"value": 0.0},
}


def coloured_quilt():
    """A quilt whose view i is filled with the value i + 1 in every channel, view 0 at the bottom left."""
    image = np.zeros((QUILT.rows * QUILT.view_height, QUILT.columns * QUILT.view_width, 3), np.uint8)
    for view in range(QUILT.views):
        row, column = QUILT.rows - 1 - view // QUILT.columns, view % QUILT.columns
        image[row * QUILT.view_height:(row + 1) * QUILT.view_height,
              column * QUILT.view_width:(column + 1) * QUILT.view_width] = view + 1
    return image


class DisplayTest(unittest.TestCase):
    def setUp(self):
        self.calibration = Calibration.from_visual(VISUAL)

    def test_reads_the_calibration_as_looking_glass_does(self):
        cal = self.calibration
        self.assertEqual((cal.width, cal.height), (1536, 2048))
        self.assertAlmostEqual(cal.pitch, 52.58790040712976 * 1536 / 324 * math.cos(math.atan(1 / -7.161397095759771)))
        self.assertAlmostEqual(cal.tilt, 2048 / (1536 * -7.161397095759771))
        self.assertAlmostEqual(cal.subp, 1 / (1536 * 3))
        self.assertTrue(cal.inverted)

    def test_a_mirrored_screen_slants_the_other_way(self):
        mirrored = Calibration.from_visual(dict(VISUAL, flipImageX={"value": 1.0}))
        self.assertAlmostEqual(mirrored.tilt, -self.calibration.tilt)
        self.assertAlmostEqual(mirrored.subp, -self.calibration.subp)

    def test_fills_the_screen(self):
        hologram = interleave(coloured_quilt(), QUILT, self.calibration)
        self.assertEqual(hologram.shape, (2048, 1536, 3))

    def test_each_sub_pixel_takes_one_view_and_every_view_is_seen(self):
        hologram = interleave(coloured_quilt(), QUILT, self.calibration)
        values = np.unique(hologram)
        self.assertEqual(values.min(), 1)
        self.assertEqual(values.max(), QUILT.views)
        self.assertEqual(len(values), QUILT.views)

    def test_the_inverted_views_go_the_other_way(self):
        quilt = coloured_quilt()
        hologram = interleave(quilt, QUILT, self.calibration).astype(int)
        other = interleave(quilt, QUILT, replace(self.calibration, inverted=False)).astype(int)
        # Mostly view v for view 47 - v; floor() at a view's edge may give the neighbouring view.
        self.assertGreater(np.mean(np.abs(hologram - 1 + other - 1 - (QUILT.views - 1)) <= 1), 0.99)


if __name__ == "__main__":
    unittest.main()
