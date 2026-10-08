# StepIt Stacker

## Table of Contents <!-- omit in toc -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Configure](#configure)
- [Run](#run)
  - [Follow the Rig](#follow-the-rig)
  - [Process a Session on Disk](#process-a-session-on-disk)
  - [Grade a Session by Hand](#grade-a-session-by-hand)
  - [The Files of a Session](#the-files-of-a-session)
- [Commands](#commands)
- [Work Inside the Container](#work-inside-the-container)
- [Troubleshooting](#troubleshooting)
- [Licences](#licences)

## Introduction

StepIt Stacker turns each session of the StepIt Macro rig, a focus stack at every angle of the stage, into a sequence of graded 16-bit images, one per angle, and shows them as a 3D image on the Looking Glass Portrait. It does this without anyone at the computer: place the subject, start the FocusStack, and come back when it is done.

For each angle, as soon as the rig has shot it:

1. **Develop.** darktable turns every raw frame (CR2) into a 16-bit linear TIFF, repairing the hot pixels.
2. **Merge.** `focus-merge` aligns the frames and merges them into one 16-bit image that is sharp everywhere.
3. **Grade.** darktable grades the merged image with a grading saved from darktable's own editor.

Once the rig has shot the whole session:

4. **Quilt.** The graded images become the 48 views of a quilt, the 3D image format of the Looking Glass.
5. **Show.** The quilt is interleaved for the Portrait, with the Portrait's own calibration, and shown full-screen on it as a hologram.

How it works is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Prerequisites

- **A PC with Ubuntu and Docker,** see [Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/). Everything runs in a Docker image built from this repo, on this PC, not on the rig.
- **The rig, reachable by ssh** as `robot@stepit.local` with this PC's key, without a password. Check it with `ssh -o BatchMode=yes robot@stepit.local true`.
- **The Looking Glass Portrait,** on HDMI and on USB-C to this PC, with a cable that carries data: its drive holds its calibration, which the desktop mounts under `/media`. In Ubuntu's display settings, set it as an extended display ("Join Displays"), in portrait orientation. No Looking Glass software is needed.

## Configure

The settings are in [`config/pipeline.toml`](config/pipeline.toml):

| Setting | Default | What it is |
|---|---|---|
| `rig.host`, `rig.user` | `stepit.local`, `robot` | The rig, for ssh and rsync. |
| `rig.port` | `9090` | The commander's rosbridge, where the rig announces each finished angle. |
| `rig.pictures` | `stepit-macro/pictures` | The rig's pictures folder, relative to the user's home on the rig. |
| `pictures.mirror` | `pictures` | Where the rig's pictures are copied and every image of a session is saved: relative to the repo, or absolute. Git ignores `pictures`. |
| `images.rotate` | `0` | Turns every merged image clockwise by 0, 90, 180 or 270 degrees. 0 keeps it as the sensor sees it, landscape. |
| `quilt.reverse` | `false` | The views go from the last angle to the first, right for the rig's stage. Set it to `true` if the depth on the Portrait looks inside out. |

The other settings of `[quilt]` are those of the Portrait. Two darktable files in `config/` set how the images are developed and graded:

- [`develop.xmp`](config/develop.xmp) develops every raw frame. It is fixed, see [Develop](docs/ARCHITECTURE.md#1-develop).
- [`grade.xmp`](config/grade.xmp) grades a session that has no grading of its own: darktable's default look for a raw file, +0.7 EV and filmic. Replace it with your own, see [Grade a Session by Hand](#grade-a-session-by-hand).

## Run

### Follow the Rig

Start the pipeline after logging in to the desktop, as it draws on the screen of that login:

```bash
./bin/pipeline.sh start
```

The first start builds the image and `focus-merge`, which takes a few minutes. Then the container `stepit-pipeline` follows the rig. Each time the rig finishes an angle, it copies the angle into `pictures`, then develops, merges and grades it. When the rig has shot the whole session, it builds the quilt and shows it on the Portrait, where it stays until the next session replaces it. Nothing goes back to the rig.

```bash
./bin/pipeline.sh logs     # follow what it does
./bin/pipeline.sh stop
```

An angle of 3 frames takes about 20 seconds on this PC, the quilt about 10 seconds.

### Process a Session on Disk

```bash
./bin/pipeline.sh session pictures/2026-10-07_12-29-19
```

A session is a folder whose `1_session` holds one folder of raw frames per angle, named so that they sort in the order of the angles, as the rig names them:

```
2026-10-07_12-29-19/
└── 1_session/
    ├── angle_01_-8.0deg/IMG_5460.CR2 ...
    ├── angle_02_-7.5deg/IMG_5465.CR2 ...
    ...
```

Angles already processed are skipped, so `session` also finishes a session that was cut short.

### Grade a Session by Hand

```bash
./bin/pipeline.sh edit pictures/2026-10-07_12-29-19
```

1. darktable opens the merged image of the angle closest to 0°, starting from the session's current grading.
2. Grade it: exposure, tone equalizer for the shadows and highlights, filmic or sigmoid for the contrast, color balance rgb for the saturation, diffuse or sharpen for the sharpness. Keep to edits of the whole image: a mask or a spot repair stays at the same place in every image while the subject turns.
3. Close darktable. The edit is saved as `grade.xmp` in the session's folder, every angle is graded with it, and the new quilt is shown.

To start every later session from this grading, copy that `grade.xmp` over `config/grade.xmp`.

### The Files of a Session

The folders are numbered in the order the pipeline makes them:

```
pictures/2026-10-07_12-29-19/
├── 1_session/                         the rig's folder of the session, copied as it is
│   ├── angle_01_-8.0deg/              the raw frames of an angle, and stack.json
│   ├── ...
│   └── all_stacks.json                once the rig has shot every angle
├── 2_merged/angle_01_-8.0deg.tif      16-bit, linear Rec.2020: the master, for grading again
├── 3_graded/angle_01_-8.0deg.tif      16-bit, sRGB: the sequence
├── 4_quilt/2026-10-07_12-29-19_qs8x6a0.75.png
└── grade.xmp                          the session's own grading, after ./bin/pipeline.sh edit
```

## Commands

`./bin/pipeline.sh` runs on the host. Every command but `start`, `stop` and `logs` runs in the running container.

| Command | What it does |
|---|---|
| `start` | Builds the image and `focus-merge`, then starts the container `stepit-pipeline`, which follows the rig. |
| `stop` | Stops it. |
| `logs` | Follows what it does. |
| `session <session>` | Processes every angle of the session not processed yet, then builds and shows its quilt. |
| `edit <session>` | Opens the session in darktable, then grades every angle with the edit and shows the quilt. |
| `grade <session>` | Grades every angle again, e.g. after a change to `grade.xmp`, then shows the quilt. |
| `quilt <session>` | Builds and shows the quilt again. |
| `show <quilt.png>` | Shows a quilt. |
| `test` | Runs the tests. |

`session`, `edit`, `grade` and `quilt` take `--no-show` to leave the Portrait as it is.

## Work Inside the Container

To change the code, start the development container with a shell:

```bash
./docker/dock.sh stepit-stacker start
```

The repo is mounted at `~/ws`, with `~/ws/bin` and `~/ws/build` on the `PATH`. `build.sh` builds `focus-merge` into `build`, and `python3 -m pipeline` runs the pipeline's commands. The home of the host user is mounted at its own path, so the pictures are found at their usual path.

> [!IMPORTANT]
> The container's user is `developer`, with password `developer`.

## Troubleshooting

**`./bin/pipeline.sh logs` shows `Connection to the rig` errors.** The rig is off, or its commander is not running: the pipeline tries again every 10 seconds, and catches up once connected. Check that the page of the rig, on port 8070, opens.

**`Cannot list the finished stacks of the rig`.** ssh to the rig failed. Check the key with `ssh -o BatchMode=yes robot@stepit.local true`.

**`frame N cannot be aligned with frame N-1`.** The alignment found nothing to lock onto: the frames show mostly blank background, or large overexposed areas. That angle gets no image, and the others go on. Frame the subject so it fills more of the picture, or reduce the exposure.

**`Cannot show the quilt on the Looking Glass`.** The quilt is saved but not shown. `no X display`: start the pipeline from the desktop's login. `no Looking Glass: no /media/*/*/LKG_calibration/visual.json`: the Portrait's USB cable is not plugged in, or carries power only; `lsusb` lists `Looking Glass Portrait` once it carries data. `No monitor of 1536 x 2048`: the Portrait is not on HDMI, or not part of the desktop in the display settings. Show the quilt again with `./bin/pipeline.sh quilt <session>`.

**The Portrait shows a grid of small images, or a blur of many views.** The hologram is drawn for another position or size: the viewer's window does not cover the Portrait exactly. `/tmp/stepit-display/viewer.log` in the container says where it went.

**The images are turned the wrong way.** Set `images.rotate`. The camera's own orientation is ignored, see [Develop](docs/ARCHITECTURE.md#1-develop).

**The depth looks inside out on the Portrait.** Set `quilt.reverse = true`, then `./bin/pipeline.sh quilt <session>`.

## Licences

StepIt Stacker is released under the MIT licence, see [`LICENSE`](LICENSE), and is a private repository. The software it uses:

| Software | Licence | Role |
|---|---|---|
| [darktable](https://www.darktable.org/) | GPL 3 | Develops and grades the images. It runs as a separate program. |
| [OpenCV](https://opencv.org/) | Apache 2.0 | Aligns and merges the frames, and makes the quilt. |
| [libtiff](https://libtiff.gitlab.io/libtiff/) | libtiff licence, BSD-like | Reads and writes the 16-bit TIFFs. |
| [GTK](https://www.gtk.org/) | LGPL 2.1 | Shows the hologram full-screen on the Portrait. |

The hologram is computed with the formula of Looking Glass's lenticular shader, as their [WebXR library](https://github.com/Looking-Glass/looking-glass-webxr) publishes it under the Apache 2.0 licence, and with the calibration read from the Portrait's own drive. No Looking Glass software is used.
