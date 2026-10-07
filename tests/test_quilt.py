"""Tests the quilt: the order of the views, the crop, and the retiming."""

import unittest

import cv2
import numpy as np

from pipeline.config import Quilt
from pipeline.quilt import assemble, retime, view

QUILT = Quilt(columns=8, rows=6, view_width=42, view_height=56, reverse=False)


def numbered(i):
    """A view filled with its own number."""
    return np.full((QUILT.view_height, QUILT.view_width, 3), i, np.float32)


class QuiltTest(unittest.TestCase):
    def test_places_the_first_view_bottom_left_and_the_last_top_right(self):
        grid = assemble([numbered(i) for i in range(QUILT.views)], QUILT)
        self.assertEqual(grid.shape, (6 * 56, 8 * 42, 3))
        self.assertEqual(grid[-1, 0, 0], 0)  # Bottom left.
        self.assertEqual(grid[-1, -1, 0], 7)  # Bottom right: the end of the first row.
        self.assertEqual(grid[0, 0, 0], 40)  # Top left: the start of the last row.
        self.assertEqual(grid[0, -1, 0], 47)  # Top right.

    def test_crops_to_the_aspect_of_a_view(self):
        landscape = np.zeros((300, 600, 3), np.uint16)
        landscape[:, 225:375] = 65535  # A band in the middle, narrower than the crop, 225 wide.
        result = view(landscape, QUILT)
        self.assertEqual(result.shape, (56, 42, 3))
        self.assertGreater(result[28, 21, 0], 60000)  # The middle is kept.
        self.assertEqual(result[28, 0, 0], 0)  # The sides are dark, not cut away into the middle.

    def test_retimes_to_the_number_of_views(self):
        rng = np.random.default_rng(3)
        texture = cv2.resize(rng.random((14, 11, 3)).astype(np.float32), (42, 56))
        views = [np.roll(texture, shift, axis=1) for shift in range(0, 35, 1)]  # 35 angles.
        result = retime(views, 48)
        self.assertEqual(len(result), 48)
        np.testing.assert_array_equal(result[0], views[0])
        np.testing.assert_array_equal(result[-1], views[-1])

    def test_repeats_a_single_view(self):
        self.assertEqual(len(retime([numbered(1)], 48)), 48)


if __name__ == "__main__":
    unittest.main()
