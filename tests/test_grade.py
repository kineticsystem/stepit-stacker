"""Tests the grading step with a stand-in for stepit-grader-cli, which records its arguments and writes the TIFF
of the picture it is given into the output folder, as stepit-grader-cli names it."""

import os
import stat
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from pipeline import grade

# The stand-in: its arguments in args.txt; the picture's TIFF in the --output folder, holding "graded"; FAIL
# makes it fail as stepit-grader-cli does, SKIP makes it write nothing.
STEPIT_GRADER_CLI = textwrap.dedent("""\
    #!/bin/bash
    printf '%s\\n' "$@" > "$(dirname "$0")/args.txt"
    [ -n "$FAIL" ] && { echo "[1/1] merged.tif: cannot read" >&2; exit 1; }
    while [ $# -gt 1 ]; do
        [ "$1" = --output ] && output="$2"
        shift
    done
    name="$(basename "${1%.*}")"
    [ -n "$SKIP" ] || echo graded > "$output/$name.tif"
""")


class GradeTest(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        tools = self.folder / "bin"
        tools.mkdir()
        self.args = tools / "args.txt"
        stand_in = tools / "stepit-grader-cli"
        stand_in.write_text(STEPIT_GRADER_CLI)
        stand_in.chmod(stand_in.stat().st_mode | stat.S_IEXEC)
        self.enterContext(mock.patch.dict(os.environ, {"PATH": f"{tools}:{os.environ['PATH']}"}))
        self.merged = self.folder / "2_merged" / "angle_01_0.0deg.tif"
        self.merged.parent.mkdir()
        self.merged.write_bytes(b"merged")
        self.graded = self.folder / "3_graded" / "angle_01_0.0deg.tif"
        self.settings = self.folder / "grade.xmp"

    def test_grades_with_the_settings_into_srgb(self):
        grade.grade(self.merged, self.graded, self.settings)
        self.assertEqual(self.graded.read_text(), "graded\n")
        arguments = self.args.read_text().splitlines()
        self.assertEqual(arguments[:2], ["--settings", str(self.settings)])
        self.assertEqual(arguments[4:6], ["--colour-space", "srgb"])
        self.assertEqual(arguments[-1], str(self.merged))
        # The TIFF is made in a folder of its own, beside the graded images, gone once done.
        self.assertEqual(Path(arguments[3]).parent, self.graded.parent)
        self.assertEqual([path.name for path in self.graded.parent.iterdir()], [self.graded.name])

    def test_replaces_the_graded_image(self):
        self.graded.parent.mkdir()
        self.graded.write_text("old")
        grade.grade(self.merged, self.graded, self.settings)
        self.assertEqual(self.graded.read_text(), "graded\n")

    def test_reports_a_failure_and_keeps_the_graded_image(self):
        self.graded.parent.mkdir()
        self.graded.write_text("old")
        with mock.patch.dict(os.environ, {"FAIL": "1"}):
            with self.assertRaisesRegex(RuntimeError, "cannot read"):
                grade.grade(self.merged, self.graded, self.settings)
        self.assertEqual(self.graded.read_text(), "old")

    def test_reports_a_tiff_not_made(self):
        with mock.patch.dict(os.environ, {"SKIP": "1"}):
            with self.assertRaisesRegex(RuntimeError, "did not grade"):
                grade.grade(self.merged, self.graded, self.settings)


if __name__ == "__main__":
    unittest.main()
