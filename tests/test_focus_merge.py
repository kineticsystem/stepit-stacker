"""Tests focus-merge on a synthetic focus stack.

The scene is a random texture whose depth grows from left to right. Each frame
is in focus at one depth, blurred elsewhere, and magnified 1.5% more than the
one before, as on the rig's rail. The merged image must be much closer to the
sharp scene than any single frame.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

FOCUS_MERGE = Path(__file__).resolve().parents[1] / "build" / "focus-merge"
FRAMES = 5
STEP = 0.015  # Magnification per frame.
WIDTH, HEIGHT = 1200, 900


def scene(rng):
    """A linear RGB texture, CV_32FC3, with detail at every scale."""
    image = np.zeros((HEIGHT, WIDTH, 3), np.float32)
    for size in (2, 4, 8, 16, 32):
        noise = rng.random((HEIGHT // size + 1, WIDTH // size + 1, 3)).astype(np.float32)
        image += cv2.resize(noise, (WIDTH, HEIGHT), interpolation=cv2.INTER_NEAREST)[:HEIGHT, :WIDTH] / 5
    return 0.05 + 0.4 * image


def magnify(image, factor):
    """The image magnified about its centre."""
    centre = ((image.shape[1] - 1) / 2, (image.shape[0] - 1) / 2)
    matrix = cv2.getRotationMatrix2D(centre, 0, factor)
    return cv2.warpAffine(image, matrix, (image.shape[1], image.shape[0]), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REFLECT)


def frame(sharp, focus):
    """The scene in focus at depth `focus`, from 0 at the left to 1 at the right."""
    depth = np.tile(np.linspace(0, 1, WIDTH, dtype=np.float32), (HEIGHT, 1))
    blur = 8 * np.abs(depth - focus)  # Blur radius, in pixels.
    result = np.zeros_like(sharp)
    weights = np.zeros((HEIGHT, WIDTH), np.float32)
    for sigma in np.arange(0, 8.5, 0.5):
        blurred = sharp if sigma == 0 else cv2.GaussianBlur(sharp, (0, 0), sigma)
        weight = np.clip(1 - np.abs(blur - sigma) / 0.5, 0, None)
        result += blurred * weight[..., None]
        weights += weight
    return result / weights[..., None]


def write16(path, image):
    cv2.imwrite(str(path), np.clip(image * 65535, 0, 65535).astype(np.uint16))


def read16(path):
    return cv2.imread(str(path), cv2.IMREAD_UNCHANGED).astype(np.float32) / 65535


def error(a, b):
    """Root mean square difference, away from the borders."""
    margin = 60
    return float(np.sqrt(np.mean((a[margin:-margin, margin:-margin] - b[margin:-margin, margin:-margin]) ** 2)))


class FocusMergeTest(unittest.TestCase):
    def test_merges_a_synthetic_stack(self):
        sharp = scene(np.random.default_rng(1))
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            frames = []
            for i in range(FRAMES):
                path = folder / f"frame_{i}.tif"
                write16(path, magnify(frame(sharp, i / (FRAMES - 1)), 1 + STEP * i))
                frames.append(path)
            merged_path = folder / "merged.tif"
            subprocess.run([str(FOCUS_MERGE), "-o", str(merged_path), *map(str, frames)], check=True)
            merged = read16(merged_path)

            # The reference is the most magnified frame, the last.
            truth = magnify(sharp, 1 + STEP * (FRAMES - 1))
            self.assertEqual(merged.shape, truth.shape)
            best_frame = min(error(read16(path), truth) for path in frames)
            merged_error = error(merged, truth)
            print(f"\nError of the best frame: {best_frame:.4f}, of the merged image: {merged_error:.4f}")
            self.assertLess(merged_error, best_frame / 2)

    def test_reports_frames_that_cannot_be_aligned(self):
        rng = np.random.default_rng(2)
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            write16(folder / "a.tif", scene(rng))
            write16(folder / "b.tif", np.full((HEIGHT, WIDTH, 3), 0.2, np.float32))
            result = subprocess.run(
                [str(FOCUS_MERGE), "-o", str(folder / "merged.tif"), str(folder / "a.tif"), str(folder / "b.tif")],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("frame 2 cannot be aligned", result.stderr)


if __name__ == "__main__":
    unittest.main()
