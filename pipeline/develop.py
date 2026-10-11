"""The develop step, run with raw-convert, of modules/raw-converter.

develop(): raw frames to 16-bit TIFF, linear Rec.2020, their bad pixels repaired.
"""

import re
import shutil
import subprocess
from pathlib import Path

# The frames each name a line "[n/N] <raw> -> <tif> (k bad pixels)", the last word only when it repaired some.
BAD_PIXELS = re.compile(r"\((\d+) bad pixels?\)")


def develop(raws, folder, defect_map=None):
    """Develops the raw frames into folder/<name>.tif, and returns those files in the same order, with the number
    of bad pixels repaired in all of them.

    The sensor's defects are found in each frame, and those of `defect_map`, when the file exists, are repaired in
    every frame. raw-convert writes back the map it is given: it gets a copy, so the map is only ever read here."""
    folder.mkdir(parents=True, exist_ok=True)
    # raw-convert takes a file or a folder: a folder of links to exactly these frames.
    inputs = folder / "raw"
    inputs.mkdir()
    for raw in raws:
        (inputs / raw.name).symlink_to(raw.resolve())
    command = ["raw-convert", "--format", "tiff", "--colour-space", "rec2020", "--bad-pixels", "image"]
    if defect_map is not None and defect_map.exists():
        copy = folder / "defects.txt"
        shutil.copyfile(defect_map, copy)
        command += ["--defect-map", str(copy)]
    result = subprocess.run([*command, str(inputs), str(folder)], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"raw-convert failed: {result.stdout[-2000:]}{result.stderr[-2000:]}")
    developed = [folder / f"{raw.stem}.tif" for raw in raws]
    missing = [path.name for path in developed if not path.exists()]
    if missing:
        raise RuntimeError(f"raw-convert did not develop {', '.join(missing)}")
    return developed, sum(int(count) for count in BAD_PIXELS.findall(result.stdout))
