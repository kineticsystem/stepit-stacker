"""Shows a quilt on the Looking Glass Portrait, as a hologram.

A Looking Glass is a screen behind a sheet of slanted lenses: each sub-pixel is
seen from one direction only. show() interleaves the quilt for the Portrait:
for each sub-pixel, it takes the view of the quilt seen from that sub-pixel's
direction, at the same place in the view. Which view that is follows from the
Portrait's calibration, which it reads from the Portrait's own drive,
LKG_calibration/visual.json, mounted under /media. The formula is the one of
Looking Glass's lenticular shader, published in their WebXR library
(https://github.com/Looking-Glass/looking-glass-webxr, Apache 2.0).

The hologram, an image of the size of the Portrait's screen, is then shown
full-screen on the Portrait by pipeline.viewer, a process of its own that runs
until the next hologram replaces it.
"""

import json
import logging
import math
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)

CALIBRATIONS = "/media/*/*/LKG_calibration/visual.json"
STATE = Path("/tmp/stepit-display")
HOLOGRAM = STATE / "hologram.png"
VIEWER_PID = STATE / "viewer.pid"
VIEWER_LOG = STATE / "viewer.log"


@dataclass(frozen=True)
class Calibration:
    """What the interleaving needs of a Looking Glass's calibration."""

    width: int  # The screen, in pixels.
    height: int
    pitch: float  # Lenses across the screen's width, along the slant.
    tilt: float  # How far the lenses slant: the horizontal shift per screen height, in screen widths.
    center: float  # Where view 0 starts under a lens, as a fraction of a lens.
    subp: float  # The width of a sub-pixel, as a fraction of the screen's width.
    inverted: bool  # The views go from right to left under each lens.

    @classmethod
    def from_visual(cls, values):
        """From the values of visual.json, each a number or {"value": number}."""
        v = {key: value["value"] if isinstance(value, dict) else value for key, value in values.items()}
        width, height = int(v["screenW"]), int(v["screenH"])
        flip = -1.0 if v.get("flipImageX", 0) else 1.0
        return cls(
            width=width,
            height=height,
            pitch=v["pitch"] * width / v["DPI"] * math.cos(math.atan(1.0 / v["slope"])),
            tilt=height / (width * v["slope"]) * flip,
            center=v["center"],
            subp=flip / (width * 3),
            inverted=bool(v.get("invView", 1)),
        )


def find_calibration():
    """The calibration of the Looking Glass whose drive is mounted under /media."""
    paths = sorted(Path("/").glob(CALIBRATIONS.lstrip("/")))
    if not paths:
        raise RuntimeError(f"no Looking Glass: no {CALIBRATIONS}, is its USB cable plugged in?")
    return Calibration.from_visual(json.loads(paths[0].read_text()))


def interleave(quilt_image, quilt, calibration):
    """The image the Portrait's screen shows for the quilt: for each sub-pixel, the view seen from its direction.

    quilt_image is a BGR image, as OpenCV reads it, with view 0 at the bottom left."""
    cal, views = calibration, quilt.views
    # Texture coordinates of each pixel's centre, y from the bottom, as in the shader.
    u = (np.arange(cal.width) + 0.5) / cal.width
    v = 1.0 - (np.arange(cal.height) + 0.5) / cal.height
    u, v = np.meshgrid(u, v)
    quilt_height, quilt_width = quilt_image.shape[:2]
    hologram = np.empty((cal.height, cal.width, 3), quilt_image.dtype)
    for subpixel in range(3):  # Red, green, blue, from the left of the pixel.
        position = np.mod((u + subpixel * cal.subp + v * cal.tilt) * cal.pitch - cal.center, 1.0)
        if cal.inverted:
            position = 1.0 - position
        view = np.minimum(np.floor(position * views), views - 1)
        x = (np.mod(view, quilt.columns) + u) / quilt.columns
        y = (np.floor(view / quilt.columns) + v) / quilt.rows  # From the bottom.
        column = np.clip((x * quilt_width).astype(np.int64), 0, quilt_width - 1)
        row = quilt_height - 1 - np.clip((y * quilt_height).astype(np.int64), 0, quilt_height - 1)
        channel = 2 - subpixel  # OpenCV's images are BGR.
        hologram[..., channel] = quilt_image[row, column, channel]
    return hologram


def stop_viewer():
    try:
        os.killpg(int(VIEWER_PID.read_text()), signal.SIGTERM)
    except (OSError, ValueError):
        pass
    VIEWER_PID.unlink(missing_ok=True)


def show(quilt_path, quilt):
    """Shows the quilt on the Portrait, replacing the hologram shown before."""
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("no X display: cannot show on the Portrait")
    calibration = find_calibration()
    quilt_image = cv2.imread(str(quilt_path), cv2.IMREAD_COLOR)
    if quilt_image is None:
        raise RuntimeError(f"cannot read {quilt_path}")
    STATE.mkdir(exist_ok=True)
    hologram = HOLOGRAM.with_suffix(".tmp.png")
    cv2.imwrite(str(hologram), interleave(quilt_image, quilt, calibration))
    hologram.replace(HOLOGRAM)

    stop_viewer()
    # Pixel for pixel, whatever the desktop's scaling.
    environment = dict(os.environ, GDK_SCALE="1", GDK_DPI_SCALE="1")
    with open(VIEWER_LOG, "wb") as output:
        viewer = subprocess.Popen(
            [sys.executable, "-m", "pipeline.viewer", str(HOLOGRAM), str(calibration.width), str(calibration.height)],
            cwd=Path(__file__).parents[1], env=environment, stdin=subprocess.DEVNULL, stdout=output,
            stderr=subprocess.STDOUT, start_new_session=True)
    VIEWER_PID.write_text(str(viewer.pid))
    # The viewer says within seconds whether the window is on the Portrait.
    for _ in range(20):
        time.sleep(0.5)
        output = VIEWER_LOG.read_text(errors="replace")
        # GTK may warn first, e.g. that there is no accessibility bus.
        if any(line.startswith("Showing") for line in output.splitlines()):
            log.info("Showing %s on the Looking Glass", quilt_path)
            return
        if viewer.poll() is not None:
            raise RuntimeError(f"the viewer stopped:\n{output.strip()}")
    raise RuntimeError(f"the viewer did not answer, see {VIEWER_LOG}")
