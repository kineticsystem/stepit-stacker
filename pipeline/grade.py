"""The grading step, run with stepit-grader-cli, of modules/stepit-grader.

grade(): a merged image to 16-bit TIFF, sRGB, with the settings of an XMP sidecar.
"""

import subprocess
import tempfile
from pathlib import Path

# sRGB: the quilt reads the graded images as sRGB, as every viewer does.
COLOUR_SPACE = "srgb"


def grade(merged, graded, settings):
    """Grades the merged image into graded, a .tif file, with the settings of the XMP file `settings`, replacing
    the graded image if it exists."""
    graded.parent.mkdir(parents=True, exist_ok=True)
    # stepit-grader-cli names its TIFF after the picture: it writes into a folder of its own, then the result
    # replaces the graded image, whole.
    with tempfile.TemporaryDirectory(dir=graded.parent, prefix=".grade-") as folder:
        command = ["stepit-grader-cli", "--settings", str(settings), "--output", folder,
                   "--colour-space", COLOUR_SPACE, str(merged)]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"stepit-grader-cli failed: {result.stdout[-2000:]}{result.stderr[-2000:]}")
        exported = Path(folder) / f"{merged.stem}.tif"
        if not exported.exists():
            raise RuntimeError(f"stepit-grader-cli did not grade {merged}")
        exported.replace(graded)
