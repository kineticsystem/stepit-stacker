"""Where the files of a session are.

A session is one 3D shoot, a folder named after when it started, e.g.
pictures/2026-10-07_12-29-19. Its folders are numbered in the order the
pipeline makes them:

    1_session/<angle>/     the rig's folder of the session, as it is: the raw
                           frames of each angle, stack.json, all_stacks.json
    2_merged/<angle>.tif   the merged image, 16-bit, linear Rec.2020
    3_graded/<angle>.tif   the graded image, 16-bit, sRGB: the sequence
    4_quilt/<session>_qs8x6a0.75.png
                           and, while the rig shoots, the quilt of the angles
                           done so far: <session>_preview_qs8x6a0.75.png
"""

import re
from pathlib import Path

RAW_EXTENSIONS = {".cr2", ".cr3", ".nef", ".arw", ".dng", ".raf", ".orf", ".rw2"}
STACK_FILE = "stack.json"
ALL_STACKS_FILE = "all_stacks.json"
RAW_FOLDER = "1_session"
MERGED_FOLDER = "2_merged"
GRADED_FOLDER = "3_graded"
QUILT_FOLDER = "4_quilt"
DEGREES = re.compile(r"_(-?\d+(?:\.\d+)?)deg$")


def raw_files(angle):
    """The raw frames of an angle, in the order they were shot."""
    return sorted(path for path in angle.iterdir() if path.suffix.lower() in RAW_EXTENSIONS)


def mirrored(mirror, folder):
    """Where a folder of the rig, relative to its pictures folder, is copied in the mirror: a session's folder
    into its 1_session, e.g. 2026-10-07_12-29-19/angle_01_-8.0deg into 2026-10-07_12-29-19/1_session/angle_01_-8.0deg."""
    session, *rest = Path(folder).parts
    return Path(mirror, session, RAW_FOLDER, *rest)


class Session:
    def __init__(self, folder):
        self.folder = Path(folder).resolve()
        self.name = self.folder.name
        self.raw = self.folder / RAW_FOLDER

    def angle(self, name):
        return self.raw / name

    def angles(self):
        """The folders of the angles that hold raw frames, in the order they were shot."""
        if not self.raw.is_dir():
            return []
        return sorted(path for path in self.raw.iterdir() if path.is_dir() and raw_files(path))

    def merged(self, angle):
        return self.folder / MERGED_FOLDER / f"{angle.name}.tif"

    def graded(self, angle):
        return self.folder / GRADED_FOLDER / f"{angle.name}.tif"

    def quilt(self, quilt):
        return self.folder / QUILT_FOLDER / f"{self.name}_qs{quilt.columns}x{quilt.rows}a{quilt.aspect:.4g}.png"

    def preview(self, quilt):
        """The quilt of the angles graded so far, while the rig shoots: not the session's quilt, whose presence says
        that the session is done."""
        return self.folder / QUILT_FOLDER / f"{self.name}_preview_qs{quilt.columns}x{quilt.rows}a{quilt.aspect:.4g}.png"

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
