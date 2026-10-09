"""Tests the watcher against a fake rig: which angles and sessions it processes, and which session it shows."""

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from pipeline import watch
from pipeline.config import Config, Quilt
from pipeline.layout import ALL_STACKS_FILE, STACK_FILE, Session, mirrored

SESSION = "2026-10-07_12-29-19"
ANGLES = ["angle_01_-1.0deg", "angle_02_1.0deg"]


class FakeRig:
    """The rig's pictures folder, in a folder of its own: copy() and copy_all_stacks() copy from it."""

    def __init__(self, folder, mirror):
        self.folder = folder
        self.mirror = mirror

    def shoot(self, session, angle):
        angle_folder = self.folder / session / angle
        angle_folder.mkdir(parents=True)
        (angle_folder / "IMG_0001.CR2").write_bytes(b"raw")
        (angle_folder / STACK_FILE).write_text(json.dumps({"files": ["IMG_0001.CR2"]}))

    def finish(self, session, angles):
        (self.folder / session / ALL_STACKS_FILE).write_text(json.dumps({"folder": session, "stacks": angles}))

    def finished(self):
        angles = sorted(str(path.parent.relative_to(self.folder)) for path in self.folder.glob(f"*/*/{STACK_FILE}"))
        sessions = sorted(path.parent.name for path in self.folder.glob(f"*/{ALL_STACKS_FILE}"))
        return angles, sessions

    def copy(self, folder):
        source, local = self.folder / folder, mirrored(self.mirror, folder)
        local.mkdir(parents=True, exist_ok=True)
        for path in source.iterdir():
            (local / path.name).write_bytes(path.read_bytes())
        return json.loads((local / STACK_FILE).read_text())

    def copy_all_stacks(self, session):
        local = mirrored(self.mirror, session)
        local.mkdir(parents=True, exist_ok=True)
        (local / ALL_STACKS_FILE).write_bytes((self.folder / session / ALL_STACKS_FILE).read_bytes())
        return json.loads((local / ALL_STACKS_FILE).read_text())


def grade(session, angle, _config):
    """Stands in for steps 1 to 3: the graded image only."""
    session.graded(angle).parent.mkdir(exist_ok=True)
    session.graded(angle).write_bytes(b"graded")


class WatcherTest(unittest.TestCase):
    def setUp(self):
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        mirror = folder / "mirror"
        config = Config(rig_host="rig", rig_port=9090, rig_pictures_port=8090, mirror=mirror,
                        rotate=0, quilt=Quilt(columns=8, rows=6, view_width=42, view_height=56, reverse=False))
        self.rig = FakeRig(folder / "rig", mirror)
        self.watcher = watch.Watcher(config)
        self.watcher.rig = self.rig
        self.processed = []
        self.finished = []
        self.previewed = []
        self.enterContext(mock.patch.object(watch, "process_angle", side_effect=self.process_angle))
        self.enterContext(mock.patch.object(watch, "finish_session", side_effect=self.finish_session))
        self.enterContext(mock.patch.object(watch, "preview_session",
                                            side_effect=lambda session, _config: self.previewed.append(
                                                [path.name for path in sorted(session.folder.glob("3_graded/*"))])))

    def process_angle(self, session, angle, config):
        self.processed.append(f"{session.name}/{angle.name}")
        grade(session, angle, config)

    def finish_session(self, session, _config, show):
        self.finished.append((session.name, show))

    def run_queue(self):
        """Handles what waits in the queue, as the worker does, in this thread."""
        while not self.watcher.queue.empty():
            kind, folder = self.watcher.queue.get()
            show = self.watcher.queued.pop((kind, folder))
            try:
                if kind == watch.SESSION:
                    self.watcher.handle_session(folder, show)
                else:
                    self.watcher.handle_angle(folder, show)
            except Exception:  # noqa: BLE001 - as the worker
                self.watcher.fail(kind, folder)

    def test_processes_each_announced_angle_and_shows_the_session_once_all_are_done(self):
        for angle in ANGLES:
            self.rig.shoot(SESSION, angle)
            self.watcher.on_stack_done(f"{SESSION}/{angle}")
            self.run_queue()
        self.assertEqual(self.finished, [])

        self.rig.finish(SESSION, ANGLES)
        self.watcher.on_all_stacks_done(SESSION)
        self.run_queue()
        self.assertEqual(self.processed, [f"{SESSION}/{angle}" for angle in ANGLES])
        self.assertEqual(self.finished, [(SESSION, True)])

    def progress(self, on=True):
        self.watcher.config = replace(self.watcher.config, display_progress=on)

    def previews(self):
        """Shows what the preview thread would, in this thread."""
        self.watcher.preview_next(timeout=0)

    def test_each_announced_angle_shows_the_angles_done_so_far(self):
        self.progress()
        for angle in ANGLES:
            self.rig.shoot(SESSION, angle)
            self.watcher.on_stack_done(f"{SESSION}/{angle}")
            self.run_queue()
            self.previews()
        self.assertEqual(self.previewed, [[f"{ANGLES[0]}.tif"], [f"{ANGLES[0]}.tif", f"{ANGLES[1]}.tif"]])

    def test_a_busy_preview_shows_the_latest_angles_once(self):
        self.progress()
        for angle in ANGLES:
            self.rig.shoot(SESSION, angle)
            self.watcher.on_stack_done(f"{SESSION}/{angle}")
        # Both angles are processed while the preview thread is busy: it shows both, once.
        self.run_queue()
        self.previews()
        self.previews()
        self.assertEqual(self.previewed, [[f"{ANGLES[0]}.tif", f"{ANGLES[1]}.tif"]])

    def test_the_angle_being_processed_is_not_queued_again(self):
        self.rig.shoot(SESSION, ANGLES[0])
        self.watcher.on_stack_done(f"{SESSION}/{ANGLES[0]}")
        key = self.watcher.queue.get()
        self.watcher.queued.pop(key)
        self.watcher.current = key
        # At a connection, the rig's latched announcement and the catch-up find the same angle.
        self.watcher.catch_up()
        self.watcher.on_stack_done(f"{SESSION}/{ANGLES[0]}")
        self.assertTrue(self.watcher.queue.empty())

    def test_no_preview_when_catching_up_or_without_progress(self):
        self.progress()
        self.rig.shoot(SESSION, ANGLES[0])
        self.watcher.catch_up()
        self.run_queue()
        self.progress(False)
        self.rig.shoot(SESSION, ANGLES[1])
        self.watcher.on_stack_done(f"{SESSION}/{ANGLES[1]}")
        self.run_queue()
        self.previews()
        self.assertEqual(len(self.processed), 2)
        self.assertEqual(self.previewed, [])

    def test_a_session_processes_the_angles_whose_announcement_was_missed(self):
        for angle in ANGLES:
            self.rig.shoot(SESSION, angle)
        self.rig.finish(SESSION, ANGLES)
        self.watcher.on_all_stacks_done(SESSION)
        self.run_queue()
        self.assertEqual(self.processed, [f"{SESSION}/{angle}" for angle in ANGLES])
        self.assertEqual(self.finished, [(SESSION, True)])

    def test_catching_up_builds_the_quilt_of_a_finished_session_without_showing_it(self):
        for angle in ANGLES:
            self.rig.shoot(SESSION, angle)
        self.rig.finish(SESSION, ANGLES)
        self.watcher.catch_up()
        self.run_queue()
        self.assertEqual(self.processed, [f"{SESSION}/{angle}" for angle in ANGLES])
        self.assertEqual(self.finished, [(SESSION, False)])

    def test_catching_up_leaves_a_session_without_all_stacks_alone(self):
        self.rig.shoot(SESSION, ANGLES[0])  # The rig stopped before the second angle.
        self.watcher.catch_up()
        self.run_queue()
        self.assertEqual(self.processed, [f"{SESSION}/{ANGLES[0]}"])
        self.assertEqual(self.finished, [])

    def test_catching_up_skips_a_session_that_has_its_quilt(self):
        for angle in ANGLES:
            self.rig.shoot(SESSION, angle)
        self.rig.finish(SESSION, ANGLES)
        session = Session(self.watcher.config.mirror / SESSION)
        for angle in ANGLES:
            self.rig.copy(f"{SESSION}/{angle}")
            grade(session, session.angle(angle), None)
        quilt = session.quilt(self.watcher.config.quilt)
        quilt.parent.mkdir()
        quilt.write_bytes(b"quilt")

        self.watcher.catch_up()
        self.run_queue()
        self.assertEqual(self.processed, [])
        self.assertEqual(self.finished, [])

    def test_a_session_the_catch_up_queued_is_shown_when_the_rig_announces_it(self):
        for angle in ANGLES:
            self.rig.shoot(SESSION, angle)
        self.rig.finish(SESSION, ANGLES)
        self.watcher.catch_up()
        self.watcher.on_all_stacks_done(SESSION)
        self.run_queue()
        self.assertEqual(self.finished, [(SESSION, True)])

    def test_ignores_a_session_with_an_unexpected_name(self):
        self.watcher.on_all_stacks_done("a/b")
        self.watcher.on_all_stacks_done("../x")
        self.watcher.on_stack_done(SESSION)
        self.watcher.on_stack_done(f"{SESSION}/{ANGLES[0]}/x")
        self.assertTrue(self.watcher.queue.empty())

    def test_copies_the_rigs_session_into_1_session(self):
        for angle in ANGLES:
            self.rig.shoot(SESSION, angle)
        self.rig.finish(SESSION, ANGLES)
        self.watcher.on_all_stacks_done(SESSION)
        self.run_queue()
        raw = self.watcher.config.mirror / SESSION / "1_session"
        self.assertTrue((raw / ALL_STACKS_FILE).exists())
        self.assertEqual([angle.name for angle in Session(raw.parent).angles()], ANGLES)
        self.assertTrue((raw.parent / "3_graded" / f"{ANGLES[0]}.tif").exists())

    def test_catching_up_every_minute_shows_a_session_whose_announcement_was_lost(self):
        self.watcher.catch_up()
        for angle in ANGLES:
            self.rig.shoot(SESSION, angle)
        self.rig.finish(SESSION, ANGLES)
        self.watcher.catch_up(periodic=True)
        self.run_queue()
        self.assertEqual(self.processed, [f"{SESSION}/{angle}" for angle in ANGLES])
        self.assertEqual(self.finished, [(SESSION, True)])

    def test_catching_up_every_minute_leaves_a_failed_angle_alone_until_the_next_connection(self):
        self.rig.shoot(SESSION, ANGLES[0])
        with mock.patch.object(watch, "process_angle", side_effect=RuntimeError("cannot be aligned")), \
                self.assertLogs(watch.log, "ERROR"):
            self.watcher.catch_up()
            self.run_queue()
        self.watcher.catch_up(periodic=True)
        self.assertTrue(self.watcher.queue.empty())
        self.watcher.catch_up()  # A new connection.
        self.run_queue()
        self.assertEqual(self.processed, [f"{SESSION}/{ANGLES[0]}"])

    def test_says_once_that_the_rig_does_not_answer(self):
        with mock.patch.object(self.rig, "finished", side_effect=OSError("no route to host")), \
                self.assertLogs(watch.log) as logs:
            self.watcher.catch_up(periodic=True)
            self.watcher.catch_up(periodic=True)
            self.watcher.catch_up(periodic=True)
        self.assertEqual(sum("Cannot list" in line for line in logs.output), 1)


if __name__ == "__main__":
    unittest.main()
