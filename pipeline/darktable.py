"""The darktable steps: the grading, run with darktable-cli, and its edit, in darktable's window.

grade():   a merged image to 16-bit TIFF, sRGB, with a grading XMP.
edit():    the edit of a grading XMP, in darktable's window.

Every run gets a fresh darktable configuration, so the settings of the
darktable used by hand never change what the pipeline does.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path


GRADE_SETTINGS = ["plugins/imageio/format/tiff/bpp=16"]


def _run(inputs, xmp, output, icc, settings):
    with tempfile.TemporaryDirectory(prefix="darktable-") as configdir:
        command = ["darktable-cli"]
        for path in inputs:
            command += ["--import", str(path)]
        command += [str(xmp), str(output), "--out-ext", "tif", "--icc-type", icc, "--core", "--configdir", configdir]
        for setting in settings:
            command += ["--conf", setting]
        result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"darktable-cli failed: {result.stdout[-2000:]}{result.stderr[-2000:]}")


def grade(merged, graded, xmp):
    """Grades the merged image into graded, a .tif file, replacing it if it exists."""
    graded.parent.mkdir(parents=True, exist_ok=True)
    # darktable never overwrites a file: it exports next to it, then the result replaces it.
    with tempfile.TemporaryDirectory(dir=graded.parent, prefix=".grade-") as folder:
        exported = Path(folder) / graded.name
        _run([merged], xmp, exported.with_suffix(""), "SRGB", GRADE_SETTINGS)
        if not exported.exists():
            raise RuntimeError(f"darktable did not grade {merged}")
        exported.replace(graded)


def edit(image, start_from, configdir):
    """Opens the image in darktable's window, starting from the grading `start_from`, and
    returns the XMP of the edit once the window is closed.

    darktable reads the edit of an image from its sidecar, <image>.xmp, and saves
    every change there; the library in memory makes it always read the sidecar.
    """
    sidecar = image.with_name(image.name + ".xmp")
    shutil.copyfile(start_from, sidecar)
    subprocess.run(["darktable", "--library", ":memory:", "--configdir", str(configdir), str(image)], check=True)
    return sidecar
