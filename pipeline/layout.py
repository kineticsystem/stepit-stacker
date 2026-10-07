"""Where the files of a session are.

A session is the rig's folder of one 3D shoot, with one folder of raw frames
per angle, e.g. pictures/2026-10-07_12-29-19/angle_01_-8.0deg/IMG_5460.CR2.
The pipeline adds, next to the angles:

    merged/<angle>.tif     the merged image, 16-bit, linear Rec.2020
    graded/<angle>.tif     the graded image, 16-bit, sRGB: the sequence
    quilt/<session>_qs8x6a0.75.png
    grade.xmp              the session's own grading, if it has one
"""

import re
from pathlib import Path

RAW_EXTENSIONS = {".cr2", ".cr3", ".nef", ".arw", ".dng", ".raf", ".orf", ".rw2"}
STACK_FILE = "stack.json"
OUTPUT_FOLDERS = {"merged", "graded", "quilt", "stacked"}
DEGREES = re.compile(r"_(-?\d+(?:\.\d+)?)deg$")


def raw_files(angle):
    """The raw frames of an angle, in the order they were shot."""
    return sorted(path for path in angle.iterdir() if path.suffix.lower() in RAW_EXTENSIONS)


class Session:
    def __init__(self, folder):
        self.folder = Path(folder).resolve()
        self.name = self.folder.name

    def angles(self):
        """The folders of the angles that hold raw frames, in the order they were shot."""
        return sorted(
            path for path in self.folder.iterdir()
            if path.is_dir() and path.name not in OUTPUT_FOLDERS and raw_files(path)
        )

    def merged(self, angle):
        return self.folder / "merged" / f"{angle.name}.tif"

    def graded(self, angle):
        return self.folder / "graded" / f"{angle.name}.tif"

    def quilt(self, quilt):
        return self.folder / "quilt" / f"{self.name}_qs{quilt.columns}x{quilt.rows}a{quilt.aspect:.4g}.png"

    def grade_xmp(self, config):
        """The session's own grading, or the default one."""
        own = self.folder / "grade.xmp"
        return own if own.exists() else config.grade_xmp

    def is_processed(self, angle):
        """Whether the angle has a graded image newer than its frames and its stack.json."""
        graded = self.graded(angle)
        if not graded.exists():
            return False
        sources = raw_files(angle) + [path for path in [angle / STACK_FILE] if path.exists()]
        return all(graded.stat().st_mtime >= path.stat().st_mtime for path in sources)

    def middle_angle(self):
        """The angle closest to 0 degrees, or the middle one if the names give no degrees."""
        angles = self.angles()
        with_degrees = [(abs(float(m.group(1))), angle) for angle in angles if (m := DEGREES.search(angle.name))]
        if with_degrees:
            return min(with_degrees)[1]
        return angles[len(angles) // 2]
