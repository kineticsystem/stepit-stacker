"""Shows a quilt on the Looking Glass Portrait, through Looking Glass Bridge.

show() starts Bridge, the service of Looking Glass that drives the display, if
it does not run yet, then plays the quilt in a loop with lkg-toolkit. The
player waits for a key press before it exits, so it runs on a pseudo-terminal
of its own, in the background, until the next quilt replaces it.
"""

import logging
import os
import pty
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

BRIDGE_URL = "http://localhost:33334"
STATE = Path("/tmp/stepit-display")
PLAYER_PID = STATE / "player.pid"
PLAYER_LOG = STATE / "player.log"
BRIDGE_LOG = STATE / "bridge.log"


def bridge_running():
    request = urllib.request.Request(f"{BRIDGE_URL}/bridge_version", data=b"{}", method="PUT")
    try:
        with urllib.request.urlopen(request, timeout=2):
            return True
    except OSError:
        return False


def start_bridge():
    if bridge_running():
        return
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("no X display: Looking Glass Bridge cannot draw on the Portrait")
    log.info("Starting Looking Glass Bridge")
    with open(BRIDGE_LOG, "ab") as output:
        subprocess.Popen(["LookingGlassBridge"], stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                         start_new_session=True)
    for _ in range(30):
        time.sleep(1)
        if bridge_running():
            return
    raise RuntimeError(f"Looking Glass Bridge did not start, see {BRIDGE_LOG}")


def stop_player():
    try:
        os.killpg(int(PLAYER_PID.read_text()), signal.SIGTERM)
    except (OSError, ValueError):
        pass
    PLAYER_PID.unlink(missing_ok=True)


def show(quilt_path, quilt):
    """Plays the quilt on the Portrait, replacing the quilt shown before."""
    STATE.mkdir(exist_ok=True)
    start_bridge()
    displays = subprocess.run(["lkg-toolkit", "-t", "list"], capture_output=True, text=True, timeout=60).stdout
    if "Display" not in displays:
        log.warning("Bridge lists no Looking Glass display:\n%s", displays.strip())
    stop_player()
    PLAYER_LOG.write_bytes(b"")
    command = [
        "lkg-toolkit", "-t", "play", "-i", str(Path(quilt_path).resolve()),
        "-c", str(quilt.columns), "-r", str(quilt.rows), "-v", str(quilt.views), "-q", f"{quilt.aspect:.4g}", "--loop",
    ]
    player = subprocess.Popen([sys.executable, "-m", "pipeline.display", *command], cwd=Path(__file__).parents[1],
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              start_new_session=True)
    PLAYER_PID.write_text(str(player.pid))
    # The player says within seconds whether Bridge took the quilt.
    for _ in range(20):
        time.sleep(1)
        output = PLAYER_LOG.read_text(errors="replace")
        if "Failed" in output or player.poll() is not None:
            raise RuntimeError(f"lkg-toolkit could not play the quilt:\n{output.strip()}")
        if "Listening for events" in output:
            log.info("Showing %s on the Looking Glass", quilt_path)
            return
    raise RuntimeError(f"lkg-toolkit did not answer, see {PLAYER_LOG}")


def _run_player(command):
    """Runs the player on a pseudo-terminal, copying what it prints into PLAYER_LOG, until it exits."""
    master, slave = pty.openpty()
    player = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave)
    os.close(slave)
    with open(PLAYER_LOG, "ab", buffering=0) as output:
        while True:
            try:
                data = os.read(master, 4096)
            except OSError:
                break
            if not data:
                break
            output.write(data)
    return player.wait()


if __name__ == "__main__":
    sys.exit(_run_player(sys.argv[1:]))
