"""Tests the develop step with a stand-in for raw-convert, which records its arguments and makes a TIFF of each
raw frame it is given, as raw-convert names them."""

import os
import stat
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from pipeline import develop

# The stand-in: its arguments in args.txt; for each raw frame of the input folder, a TIFF, and the line
# raw-convert prints, with 3 bad pixels repaired; a line added to the defect map, as raw-convert writes it back.
# FAIL makes it fail, SKIP makes it leave out the frame of that name.
RAW_CONVERT = textwrap.dedent("""\
    #!/bin/bash
    printf '%s\\n' "$@" > "$(dirname "$0")/args.txt"
    [ -n "$FAIL" ] && { echo "IMG_0002.CR2: cannot decode" >&2; exit 1; }
    while [ $# -gt 2 ]; do
        [ "$1" = --defect-map ] && echo "1 2" >> "$2"
        shift
    done
    for raw in "$1"/*; do
        name="$(basename "${raw%.*}")"
        [ "$name" = "$SKIP" ] && continue
        touch "$2/$name.tif"
        echo "[1/1] $raw -> $2/$name.tif (3 bad pixels)"
    done
""")


class DevelopTest(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        tools = self.folder / "bin"
        tools.mkdir()
        self.args = tools / "args.txt"
        stand_in = tools / "raw-convert"
        stand_in.write_text(RAW_CONVERT)
        stand_in.chmod(stand_in.stat().st_mode | stat.S_IEXEC)
        self.enterContext(mock.patch.dict(os.environ, {"PATH": f"{tools}:{os.environ['PATH']}"}))
        self.angle = self.folder / "angle_01_0.0deg"
        self.angle.mkdir()
        # The angle's frames, among the other files of its folder.
        self.raws = [self.angle / f"IMG_000{n}.CR2" for n in (1, 2, 3)]
        for raw in self.raws:
            raw.write_bytes(b"raw")
        (self.angle / "stack.json").write_text("{}")

    def arguments(self):
        return self.args.read_text().splitlines()

    def test_develops_each_frame_in_order(self):
        frames, bad_pixels = develop.develop(self.raws, self.folder / "out")
        self.assertEqual(frames, [self.folder / "out" / f"IMG_000{n}.tif" for n in (1, 2, 3)])
        self.assertEqual(bad_pixels, 9)
        arguments = self.arguments()
        self.assertEqual(arguments[:8], ["--format", "tiff", "--colour-space", "rec2020", "--bad-pixels", "image",
                                         str(self.folder / "out" / "raw"), str(self.folder / "out")])
        # The input is the frames alone, not the rest of the angle's folder.
        self.assertEqual(sorted(path.name for path in (self.folder / "out" / "raw").iterdir()),
                         ["IMG_0001.CR2", "IMG_0002.CR2", "IMG_0003.CR2"])

    def test_repairs_the_known_defects_from_a_copy_of_the_map(self):
        defects = self.folder / "defects.txt"
        defects.write_text("camera Canon EOS 5D Mark II|1234|5634x3753\n10 20\n")
        develop.develop(self.raws, self.folder / "out", defects)
        arguments = self.arguments()
        copy = Path(arguments[arguments.index("--defect-map") + 1])
        self.assertNotEqual(copy, defects)
        self.assertEqual(copy.read_text(), "camera Canon EOS 5D Mark II|1234|5634x3753\n10 20\n1 2\n")
        # raw-convert wrote back its copy: the map is as it was.
        self.assertEqual(defects.read_text(), "camera Canon EOS 5D Mark II|1234|5634x3753\n10 20\n")

    def test_a_map_that_does_not_exist_is_left_out(self):
        develop.develop(self.raws, self.folder / "out", self.folder / "defects.txt")
        self.assertNotIn("--defect-map", self.arguments())
        self.assertFalse((self.folder / "defects.txt").exists())

    def test_a_failure_is_reported(self):
        with mock.patch.dict(os.environ, {"FAIL": "1"}), self.assertRaisesRegex(RuntimeError, "cannot decode"):
            develop.develop(self.raws, self.folder / "out")

    def test_a_missing_frame_is_reported(self):
        with mock.patch.dict(os.environ, {"SKIP": "IMG_0002"}), \
                self.assertRaisesRegex(RuntimeError, "did not develop IMG_0002.tif"):
            develop.develop(self.raws, self.folder / "out")


if __name__ == "__main__":
    unittest.main()
