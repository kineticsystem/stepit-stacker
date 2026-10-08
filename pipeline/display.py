"""Shows a quilt on the Looking Glass Portrait, with StepIt Holo, the submodule modules/stepit-holo.

show() runs `stepit-holo show` on the quilt, in a process of its own: it finds
the Portrait's calibration on the Portrait's drive, turns the quilt into the
image the Portrait's screen shows, and shows it full-screen on the Portrait,
until the next quilt replaces it. See modules/stepit-holo/README.md.
"""

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .config import REPO

log = logging.getLogger(__name__)

STEPIT_HOLO = REPO / "modules" / "stepit-holo"
STATE = Path("/tmp/stepit-display")
VIEWER_PID = STATE / "viewer.pid"
VIEWER_LOG = STATE / "viewer.log"
# The first quilt of a layout also works out StepIt Holo's table: a few seconds at most.
WAIT_S = 30


def stop_viewer():
    try:
        os.killpg(int(VIEWER_PID.read_text()), signal.SIGTERM)
    except (OSError, ValueError):
        pass
    VIEWER_PID.unlink(missing_ok=True)


def show(quilt_path, quilt, stepit_holo=STEPIT_HOLO):
    """Shows the quilt on the Portrait, replacing the quilt shown before."""
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        raise RuntimeError("no desktop: cannot show on the Portrait")
    if not (stepit_holo / "stepit_holo").is_dir():
        raise RuntimeError(f"StepIt Holo is missing from {stepit_holo}: run git submodule update --init")
    STATE.mkdir(exist_ok=True)
    stop_viewer()
    command = [sys.executable, "-m", "stepit_holo", "show", str(Path(quilt_path).resolve()),
               "--columns", str(quilt.columns), "--rows", str(quilt.rows)]
    with open(VIEWER_LOG, "wb") as output:
        viewer = subprocess.Popen(command, cwd=stepit_holo, stdin=subprocess.DEVNULL, stdout=output,
                                  stderr=subprocess.STDOUT, start_new_session=True)
    VIEWER_PID.write_text(str(viewer.pid))
    for _ in range(WAIT_S * 2):
        time.sleep(0.5)
        output = VIEWER_LOG.read_text(errors="replace")
        # GTK may warn first, e.g. that there is no accessibility bus.
        if any(line.startswith("Showing") for line in output.splitlines()):
            log.info("Showing %s on the Looking Glass", quilt_path)
            return
        if viewer.poll() is not None:
            raise RuntimeError(f"stepit-holo stopped:\n{output.strip()}")
    raise RuntimeError(f"stepit-holo did not answer, see {VIEWER_LOG}")
