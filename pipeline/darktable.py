"""The two darktable steps, run with darktable-cli.

develop(): raw frames to 16-bit TIFF, linear Rec.2020, with develop.xmp.
grade():   a merged image to 16-bit TIFF, sRGB, with a grading XMP.

Every run gets a fresh darktable configuration, so the settings of the
darktable used by hand never change what the pipeline does.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path


# 16-bit TIFF. The chromatic adaptation "legacy" makes darktable use the white
# balance the camera recorded, and the workflow "none" stops it from adding its
# default exposure and tone curve to the frames.
DEVELOP_SETTINGS = [
    "plugins/imageio/format/tiff/bpp=16",
    "plugins/darkroom/chromatic-adaptation=legacy",
    "plugins/darkroom/workflow=none",
]
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


def develop(raws, folder, xmp):
    """Develops the raw frames into folder/<name>.tif, and returns those files in the same order."""
    folder.mkdir(parents=True, exist_ok=True)
    # $(FILE_NAME) is darktable's variable for the name of each input, without its extension.
    _run(raws, xmp, folder / "$(FILE_NAME)", "LIN_REC2020", DEVELOP_SETTINGS)
    developed = [folder / f"{raw.stem}.tif" for raw in raws]
    missing = [path.name for path in developed if not path.exists()]
    if missing:
        raise RuntimeError(f"darktable did not develop {', '.join(missing)}")
    return developed


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
