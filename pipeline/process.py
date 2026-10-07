"""The steps of the pipeline, for one angle and for a whole session.

An angle:   develop its raw frames, merge them, grade the merged image.
A session:  every angle not processed yet, then the quilt, shown on the Portrait.
"""

import logging
import shutil
import tempfile
import time
from pathlib import Path

from . import darktable, display, merge, quilt
from .config import REPO
from .layout import raw_files

log = logging.getLogger(__name__)


def process_angle(session, angle, config):
    started = time.monotonic()
    raws = raw_files(angle)
    # The developed frames, 100 MB each, are only needed for the merge.
    with tempfile.TemporaryDirectory(dir=session.folder, prefix=".develop-") as folder:
        frames = darktable.develop(raws, Path(folder), config.develop_xmp)
        log.info("%s: developed %d frames in %.0f s", angle.name, len(frames), time.monotonic() - started)
        merge.merge(frames, session.merged(angle), config.rotate)
        log.info("%s: merged in %.0f s", angle.name, time.monotonic() - started)
    grade_angle(session, angle, config)
    log.info("%s: done in %.0f s, %s", angle.name, time.monotonic() - started, session.graded(angle))


def grade_angle(session, angle, config):
    darktable.grade(session.merged(angle), session.graded(angle), session.grade_xmp(config))


def finish_session(session, config, show=True):
    """Builds the quilt of the session's graded images, and shows it on the Portrait."""
    angles = session.angles()
    graded = [session.graded(angle) for angle in angles if session.graded(angle).exists()]
    if not graded:
        raise RuntimeError(f"{session.name} has no graded image")
    if len(graded) < len(angles):
        log.warning("%s: only %d of %d angles have a graded image", session.name, len(graded), len(angles))
    path = quilt.build(graded, session.quilt(config.quilt), config.quilt)
    log.info("%s: quilt of %d angles, %s", session.name, len(graded), path)
    if show:
        try:
            display.show(path, config.quilt)
        except RuntimeError as error:
            log.error("Cannot show the quilt on the Looking Glass: %s", error)
    return path


def process_session(session, config, show=True):
    """Processes every angle that is not processed yet, then finishes the session."""
    for angle in session.angles():
        if session.is_processed(angle):
            log.info("%s: processed already", angle.name)
            continue
        try:
            process_angle(session, angle, config)
        except Exception:  # noqa: BLE001 - one bad angle must not stop the others
            log.exception("%s failed", angle.name)
    return finish_session(session, config, show)


def grade_session(session, config, show=True):
    """Grades every merged image of the session again, e.g. after a new grade.xmp, then finishes the session."""
    xmp = session.grade_xmp(config)
    log.info("%s: grading with %s", session.name, xmp)
    for angle in session.angles():
        if session.merged(angle).exists():
            grade_angle(session, angle, config)
    return finish_session(session, config, show)


def edit_session(session, config, show=True):
    """Opens the merged image of the angle closest to 0 degrees in darktable, saves the edit as the
    session's grade.xmp once darktable is closed, then grades the session with it."""
    angle = session.middle_angle()
    start_from = session.grade_xmp(config)
    log.info("%s: editing %s in darktable, starting from %s", session.name, angle.name, start_from)
    sidecar = darktable.edit(session.merged(angle), start_from, REPO / ".darktable")
    shutil.copyfile(sidecar, session.folder / "grade.xmp")
    sidecar.unlink()
    log.info("%s: saved the edit as %s", session.name, session.folder / "grade.xmp")
    return grade_session(session, config, show)
