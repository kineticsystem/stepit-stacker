# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repository Is

StepIt Stacker turns each session of the StepIt Macro rig, a focus stack at every angle of the stage, into a sequence of graded 16-bit images, one per angle, and shows them as a 3D image on the Looking Glass Portrait, with no one at the computer. For each angle: develop the raw frames (`raw-convert`), merge them into one sharp image (`focus-merge`, ours, in `src/`), grade it (`stepit-grader-cli`); for each session: build a quilt and show it through StepIt Holo's server. How it is built: [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md); how to run it: the [README](../README.md).

## Working Environment

Everything runs in a Docker image built from this repo, on a PC, not on the rig. `./bin/pipeline.sh` runs on the host; every command but `start`, `stop` and `logs` runs in the running container `stepit-pipeline`:

```bash
./bin/pipeline.sh start                     # build the image and the tools, then follow the rig
./bin/pipeline.sh logs
./bin/pipeline.sh session pictures/<session>  # process a session on disk
./bin/pipeline.sh grade pictures/<session>    # grade again, e.g. after a new config/grade.xmp
./bin/pipeline.sh test                      # python3 -m unittest discover -v tests, in the container
./bin/pipeline.sh stop
```

To change the code, use the development container: `./docker/dock.sh stepit-stacker start`. The repo is mounted at `~/ws`, with `~/ws/bin` and `~/ws/build` on the `PATH`; `build.sh` builds `raw-convert` and `focus-merge` into `build`, and `python3 -m pipeline` runs the commands. The submodules `modules/raw-converter` and `modules/stepit-grader` must be present: `git submodule update --init --recursive`.

The settings are in `config/pipeline.toml`; `config/grade.xmp` grades every image; `config/defects.txt`, when made, lists the camera's known defects.

## Architecture

It follows one idea: **the rig only shoots, and says when an angle and a session are complete; everything else happens on this computer**. The rig knows nothing about StepIt Stacker, and nothing goes back to it.

- `pipeline/`, Python: `watch.py` follows the rig, one angle or session at a time; `rig.py` talks to it (its topics through rosbridge, its pictures over HTTP from StepIt Camera's web server); `process.py` chains the steps; `develop.py`, `merge.py`, `grade.py`, `quilt.py`, `display.py` are the steps; `layout.py` says where the files of a session are; `config.py` reads `pipeline.toml`.
- `src/`, C++17: `focus-merge`, which aligns and merges the frames of an angle.
- `modules/raw-converter` and `modules/stepit-grader`: our own tools, as submodules, built with the rest; StepIt Grader without Qt, its command line only. Their own tests run in their repositories: a step here is tested against a stand-in for the tool.

Easy to break:

- **The numbered folders of a session** (`1_session`, `2_merged`, `3_graded`, `4_quilt`) are known to `layout.py` only: change it there, not as a path in a step.
- **Angles already processed are skipped**, so `session` and the catch-up can finish a session cut short.
- **A display that fails does not fail the angle**: the quilt is saved either way.

## Architecture and Review Documents

For the `architect` and `reviewer` skills: what they cannot find out alone.

- `docs/ARCHITECTURE.md` follows the one idea above. Its sections, in order: Introduction, The Big Picture, The Parts (a table of path and role), The Pipeline (one subsection per step, numbered as in the README), The Watcher, The Containers, Tests (the automated tests, and a table of what is checked by hand), How to Extend StepIt Stacker, Design Decisions and Trade-offs.
- The review goes in `docs/Review.md`, the skill's default.
- Do not review the submodules here: they have their own repositories, documents and reviews.
- **Probes run in the container**: a throwaway test is a `unittest` file in `tests/`, run with `./bin/pipeline.sh test` or, in the development container, `python3 -m unittest -v tests.<module>`. The rig's side is tested in StepIt Macro; the WebSocket to the rig has no automated test.

## Conventions

- Update the README (settings, commands, troubleshooting) and `docs/ARCHITECTURE.md` when a step, a setting or a folder of a session changes.
