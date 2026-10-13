# StepIt Stacker

## Table of Contents <!-- omit in toc -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Configure](#configure)
  - [The Camera's Known Defects](#the-cameras-known-defects)
- [Run](#run)
  - [Follow the Rig](#follow-the-rig)
  - [Process a Session on Disk](#process-a-session-on-disk)
  - [Grade the Sessions](#grade-the-sessions)
  - [The Files of a Session](#the-files-of-a-session)
- [Commands](#commands)
- [Work Inside the Container](#work-inside-the-container)
- [Troubleshooting](#troubleshooting)
- [Licences](#licences)

## Introduction

StepIt Stacker turns each session of the StepIt Macro rig, a focus stack at every angle of the stage, into a sequence of graded 16-bit images, one per angle, and shows them as a 3D image on the Looking Glass Portrait. It does this without anyone at the computer: place the subject, start the FocusStack, and come back when it is done.

For each angle, as soon as the rig has shot it:

1. **Develop.** `raw-convert`, of our module [raw-converter](https://github.com/kineticsystem/raw-converter), turns every raw frame (CR2) into a 16-bit linear TIFF, repairing the hot and dead pixels.
2. **Merge.** `focus-merge` aligns the frames and merges them into one 16-bit image that is sharp everywhere.
3. **Grade.** `stepit-grader-cli`, of our module [StepIt Grader](https://github.com/kineticsystem/stepit-grader), grades the merged image with a grading saved from StepIt Grader's editor.

Once the rig has shot the whole session:

4. **Quilt.** The graded images become the 48 views of a quilt, the 3D image format of the Looking Glass.
5. **Show.** The quilt is uploaded to [StepIt Holo](https://github.com/kineticsystem/stepit-holo)'s server, on the Raspberry Pi the Portrait is plugged into, `holo`, which shows it on the Portrait as a hologram, with the Portrait's own calibration.

How it works is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Prerequisites

- **A PC with Ubuntu and Docker,** see [Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/). Everything runs in a Docker image built from this repo, on this PC, not on the rig.
- **The rig, on the network** as `stepit.local`: its rosbridge on port 9090, and StepIt Camera's web server on port 8090, which serves its pictures. No key or password is needed. Check it with `curl http://stepit.local:8090/pictures/`.
- **The Looking Glass Portrait, with StepIt Holo's server,** on the Raspberry Pi the Portrait is plugged into, on HDMI and USB: `holo`, a Raspberry Pi 5 of its own, at `http://holo.local:8095`. See [Run the Server in Docker](https://github.com/kineticsystem/stepit-holo#run-the-server-in-docker) in StepIt Holo's README. Check it with `curl http://holo.local:8095/status`. Without it, the pipeline makes the quilts, and says it cannot show them.

## Configure

The settings are in [`config/pipeline.toml`](config/pipeline.toml):

| Setting | Default | What it is |
|---|---|---|
| `rig.host` | `stepit.local` | The rig. |
| `rig.port` | `9090` | The commander's rosbridge, where the rig announces each finished angle. |
| `rig.pictures_port` | `8090` | StepIt Camera's web server on the rig, which serves the rig's pictures folder at `/pictures/`. |
| `pictures.mirror` | `pictures` | Where the rig's pictures are copied and every image of a session is saved: relative to the repo, or absolute. Git ignores `pictures`. |
| `develop.defect_map` | `config/defects.txt` | The camera's known defects, repaired in every frame, when the file exists. See [The Camera's Known Defects](#the-cameras-known-defects). |
| `images.rotate` | `90` | Turns every merged image clockwise by 0, 90, 180 or 270 degrees. 0 keeps it as the sensor sees it, landscape. On the rig, the stage's turn moves the subject up and down in the sensor's picture, and the Portrait shows its views from side to side: 90 makes the turn sideways. |
| `quilt.reverse` | `false` | The views go from the last angle to the first, right for the rig's stage. Set it to `true` if the depth on the Portrait looks inside out. |
| `quilt.interpolation` | `nearest` | How a view between two angles is made: `nearest` warps the nearer angle toward it along the optical flow; `blend` warps both and blends them, which shows ghosts where the flow fails, e.g. thin legs crossing. |
| `display.url` | `http://holo.local:8095` | StepIt Holo's server, which shows each quilt on the Portrait. |
| `display.progress` | `true` | While the rig shoots, shows the quilt of the angles done so far: flat after the first angle, with depth from the second. `false` leaves the last session on the Portrait until the new one is complete. |

The other settings of `[quilt]` are those of the Portrait. One file in `config/` sets how every image of every session is graded: [`grade.xmp`](config/grade.xmp), a sidecar of StepIt Grader. The one in the repo makes no edit: the merged image, only turned into sRGB. Replace it with your own, see [Grade the Sessions](#grade-the-sessions).

### The Camera's Known Defects

The development repairs the hot and dead pixels it finds in each frame. A faint one, a warm pixel only a few times brighter than its neighbours, could also be detail of the subject: it is repaired only once photos of different scenes show it. Each angle is one scene, so learn them once, from 10 or more photos of different scenes taken with the rig's camera, at the rig's ISO and exposure, e.g. a dark frame with the lens cap on, and a few of anything. With the pipeline running, and the photos in a folder of the home:

```bash
docker exec -w /home/developer/ws stepit-pipeline \
    raw-convert --bad-pixels batch --defect-map config/defects.txt ~/Pictures/rig-defects /tmp/defects
```

`config/defects.txt` lists the defects found in at least two scenes, by camera body. Without it, the development repairs the defects that stand out in each frame alone.

## Run

### Follow the Rig

Start the pipeline:

```bash
./bin/pipeline.sh start
```

The first start fetches the raw-converter and stepit-grader modules, and builds the image, `raw-convert`, `focus-merge` and `stepit-grader-cli`, which takes a few minutes. Then the container `stepit-pipeline` follows the rig. Each time the rig finishes an angle, it copies the angle into `pictures`, then develops, merges and grades it. While the rig shoots, it shows on the Portrait the quilt of the angles done so far: flat after the first angle, then with a depth that grows as the stage turns. When the rig has shot the whole session, it builds the quilt and shows it on the Portrait, where it stays until the next session replaces it. Nothing goes back to the rig.

```bash
./bin/pipeline.sh logs     # follow what it does
./bin/pipeline.sh stop
```

An angle of 10 frames takes about 25 seconds on this PC, the quilt about 10 seconds.

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

### Grade the Sessions

Every angle of every session is graded with `config/grade.xmp`. To make your own grading, with [StepIt Grader](https://github.com/kineticsystem/stepit-grader) installed on the desktop:

1. Open a merged image of a session in StepIt Grader, e.g. that of the angle closest to 0°, `pictures/2026-10-07_12-29-19/2_merged/angle_18_0.0deg.tif`.
2. Start from the camera's look: choose **Edit > Match Camera Look…** and pick two or three raw frames of the same angle, e.g. from `pictures/2026-10-07_12-29-19/1_session/angle_18_0.0deg/`. Each frame holds the JPEG the camera made of it; StepIt Grader finds the grade that makes the frames look like those JPEGs, in about 20 seconds a frame, then **Apply** sets it. The merged image has the tones of the frames it was made from, so their grade fits it.
3. Adjust what the subject needs: the white balance, with the eyedropper at the top of **Color** on something white or grey, the exposure, the contrast, the highlights and shadows, the vibrance and saturation, the tone curve, the colour mixer, the sharpness. Every tool works on the whole image: none stays at one place while the subject turns.
4. Save the settings, `Ctrl+S`, or wait a second: StepIt Grader writes them next to the image, as `angle_18_0.0deg.tif.xmp`, the TIFF's whole name with `.xmp`.
5. Copy that file over `config/grade.xmp`, and grade the session again:

   ```bash
   cp pictures/2026-10-07_12-29-19/2_merged/angle_18_0.0deg.tif.xmp config/grade.xmp
   ./bin/pipeline.sh grade pictures/2026-10-07_12-29-19
   ```

> [!IMPORTANT]
> Turn the camera's Auto Lighting Optimizer off for the frames you match: it changes each JPEG by its content, so no grade can match it. The raw frames, which the pipeline develops, are the same either way.

Every later session is graded the same way. To go back to no edit, `git checkout config/grade.xmp`.

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
│                                      while the rig shoots, also ..._preview_qs8x6a0.75.png,
│                                      the quilt of the angles done so far
```

## Commands

`./bin/pipeline.sh` runs on the host. Every command but `start`, `stop` and `logs` runs in the running container.

| Command | What it does |
|---|---|
| `start` | Builds the image and `focus-merge`, then starts the container `stepit-pipeline`, which follows the rig. |
| `stop` | Stops it. |
| `logs` | Follows what it does. |
| `session <session>` | Processes every angle of the session not processed yet, then builds and shows its quilt. |
| `grade <session>` | Grades every angle again, e.g. after a change to `grade.xmp`, then shows the quilt. |
| `quilt <session>` | Builds and shows the quilt again. |
| `show <quilt.png>` | Shows a quilt. |
| `test` | Runs the tests. |

`session`, `grade` and `quilt` take `--no-show` to leave the Portrait as it is.

## Work Inside the Container

To change the code, start the development container with a shell:

```bash
./docker/dock.sh stepit-stacker start
```

The repo is mounted at `~/ws`, with `~/ws/bin` and `~/ws/build` on the `PATH`. `build.sh` builds `raw-convert` and `focus-merge` into `build`, and `python3 -m pipeline` runs the pipeline's commands. The home of the host user is mounted at its own path, so the pictures are found at their usual path.

> [!IMPORTANT]
> The container's user is `developer`, with password `developer`.

## Troubleshooting

**`./bin/pipeline.sh logs` shows `Connection to the rig` errors.** The rig is off, or its commander is not running: the pipeline tries again every 10 seconds, and catches up once connected. Check that the page of the rig, on port 8070, opens.

**`Cannot list the finished stacks of the rig`.** StepIt Camera's web server did not answer: the rig is off, or its camera's web server is not running. Check it with `curl http://stepit.local:8090/pictures/`. A `404` means a StepIt Camera from before its folder listing: update the rig.

**`frame N cannot be aligned with frame N-1`.** The alignment found nothing to lock onto: the frames show mostly blank background, or large overexposed areas. That angle gets no image, and the others go on. Frame the subject so it fills more of the picture, or reduce the exposure.

**`Cannot show the quilt on the Looking Glass`.** The quilt is saved but not shown. `cannot reach StepIt Holo`: its server is not running, or `display.url` is wrong; check it with `curl http://holo.local:8095/status`. `refused`, followed by the server's message: the quilt is not one it can read. Show the quilt again with `./bin/pipeline.sh quilt <session>`.

**`StepIt Holo keeps <quilt>, and shows it once it can`.** The server has the quilt, but cannot show it yet, e.g. `no Looking Glass found` or `no screen of 1536 x 2048`: the Portrait is switched off or unplugged. The server shows it as soon as the Portrait is back, with nothing to do here; its [Troubleshooting](https://github.com/kineticsystem/stepit-holo#troubleshooting) says what to check.

**The Portrait shows a grid of small images, or a blur of many views.** The hologram does not fall on the Portrait's lenses as it should. Check the Portrait with StepIt Holo's test quilt, `curl -X POST http://holo.local:8095/numbers`, and its [Troubleshooting](https://github.com/kineticsystem/stepit-holo#troubleshooting).

**The Portrait shows a moving picture, not depth, as the head moves sideways.** The views move up and down instead of sideways: the stage's turn is not horizontal in the images. Set `images.rotate` to 90 or 270, then process the session again. If the depth then looks inside out, use the other of the two.

**The images are turned the wrong way.** Set `images.rotate`. The camera's own orientation is ignored, see [Develop](docs/ARCHITECTURE.md#1-develop).

**The depth looks inside out on the Portrait.** Set `quilt.reverse = true`, then `./bin/pipeline.sh quilt <session>`.

## Licences

StepIt Stacker is released under the MIT licence, see [`LICENSE`](LICENSE), and is a private repository. The software it uses:

| Software | Licence | Role |
|---|---|---|
| [raw-converter](https://github.com/kineticsystem/raw-converter) | MIT | Develops the raw frames: `raw-convert`, our own module, built from source. |
| [LibRaw](https://www.libraw.org/) | LGPL 2.1 or CDDL 1.0 | Decodes and demosaics the raw frames, in `raw-convert`, linked dynamically. |
| [Little CMS](https://www.littlecms.com/) | MIT | Makes the ICC profiles of the developed frames, in `raw-convert`. |
| [StepIt Grader](https://github.com/kineticsystem/stepit-grader) | MIT | Grades the images: `stepit-grader-cli`, our own module, built from source. |
| [pugixml](https://pugixml.org/) | MIT | Reads the grading's XMP file, in `stepit-grader-cli`. |
| [OpenCV](https://opencv.org/) | Apache 2.0 | Aligns and merges the frames, and makes the quilt. |
| [libtiff](https://libtiff.gitlab.io/libtiff/) | libtiff licence, BSD-like | Reads and writes the 16-bit TIFFs. |
| [StepIt Holo](https://github.com/kineticsystem/stepit-holo) | MIT | Shows the quilt on the Portrait. It runs as a server of its own, on the computer of the Portrait. |
