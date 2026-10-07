# StepIt Stacker

## Table of Contents <!-- omit in toc -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Install StepIt Stacker](#install-stepit-stacker)
  - [Build the Project](#build-the-project)
  - [Work Inside the Container](#work-inside-the-container)
- [Running the Application](#running-the-application)
  - [Merge the Stacks as the Rig Shoots Them](#merge-the-stacks-as-the-rig-shoots-them)
  - [Copy the Pictures from the Rig](#copy-the-pictures-from-the-rig)
  - [Stack a Session](#stack-a-session)
  - [Stack One Angle](#stack-one-angle)
- [Parameters](#parameters)
- [How It Works](#how-it-works)
  - [Hot and Dead Pixels](#hot-and-dead-pixels)
  - [Brightness and Colours](#brightness-and-colours)
  - [Alignment](#alignment)
  - [The Watcher](#the-watcher)
- [Troubleshooting](#troubleshooting)
- [Licences](#licences)

## Introduction

Stack merges the focus stacks shot by the StepIt Macro rig into one sharp image each, as Zerene Stacker does. It is a C++ command line tool built on open-source libraries whose licences are compatible with MIT.

- It reads the raw files of the camera, CR2 for the Canon 5D Mark II, and any other format LibRaw reads.
- It repairs the hot and dead pixels of the sensor automatically, as Adobe's raw converters do.
- It gives the images the brightness and colours of the camera's own JPEG, as we see the shots on screen.
- It aligns the frames of each stack, then keeps the sharpest detail of each frame.
- It merges every stack found in a folder in one run: one folder per angle, one image per angle.
- It can follow the rig and merge each stack as soon as the rig has shot it, while the rig shoots the next one.

## Prerequisites

We need a computer with Ubuntu 24.04 and Docker. Please refer to the document [Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/).

StepIt Stacker runs on this PC, not on the rig computer: the rig only shoots and stores the pictures, and the merge needs about 3.5 GB of memory per stack and all the cores it can get.

## Install StepIt Stacker

### Build the Project

Build the image and the container, from anywhere:

```
./docker/dock.sh stepit-stacker build
```

Build the stacker inside the container, into `./build`:

```
docker run --rm -v "$PWD:/home/developer/ws" stepit-stacker:latest build.sh
```

The first build downloads [focus-stack](https://github.com/PetteriAimonen/focus-stack) at a fixed commit, so it needs internet access. The command `./bin/stack.sh` builds the image and the stacker on its first run if they are missing, so this step is optional.

### Work Inside the Container

To change the code, start the container with an interactive shell:

```
./docker/dock.sh stepit-stacker start
```

Inside the container, the repo is mounted at `~/ws`, and `~/ws/bin` and `~/ws/build` are on the `PATH`, so `build.sh` and `stack` work from any directory. The home of the host user is mounted at the same path, so the pictures are found at their usual path.

> [!IMPORTANT]
> The docker container provides a default user `developer` with password `developer`.

## Running the Application

### Merge the Stacks as the Rig Shoots Them

Start the watcher once; Docker starts it again with the computer, until it is stopped:

```
./bin/watcher.sh start
```

Each time the rig finishes the stack of an angle, the watcher copies its pictures and merges them. The images land in this repo, in `pictures`, a mirror of the rig's pictures folder that git ignores, in a `stacked` folder next to the pictures of the session:

```
pictures/2026-10-07_12-29-19/
├── angle_01_0.0deg/            the pictures, copied from the rig, and stack.json
├── angle_02_0.0deg/
└── stacked/
    ├── angle_01_0.0deg.tif
    └── angle_02_0.0deg.tif
```

Nothing goes back to the rig. A stack of 12 frames is merged about 40 seconds after the rig finished it.

Follow what it does, and stop it:

```
./bin/watcher.sh logs
./bin/watcher.sh stop
```

The options after `--` go to the stacker for every stack, e.g. `./bin/watcher.sh start -- --depthmap`. `STACK_MIRROR` sets another mirror, `STACK_RIG` another rig, e.g. `STACK_RIG=192.168.100.25 ./bin/watcher.sh start`. See [The Watcher](#the-watcher) for how it works.

### Copy the Pictures from the Rig

The rig stores the pictures in `~/stepit-macro/pictures` on `stepit.local`, one folder per session, then one folder per angle. Copy them into this repo first:

```
rsync -a robot@stepit.local:stepit-macro/pictures/ pictures/
```

`rsync` only copies the sessions that are new or changed, so we can run it after every shoot.

### Stack a Session

Give the stacker a session folder:

```
./bin/stack.sh pictures/2026-10-07_12-13-58
```

It finds every folder of raw files below the session, merges each one, and saves the images in `stacked`, named after the angles:

```
2026-10-07_12-13-58/
├── angle_01_0.0deg/
├── angle_02_0.0deg/
└── stacked/
    ├── angle_01_0.0deg.tif
    └── angle_02_0.0deg.tif
```

A stack of 5 frames takes about 20 seconds. The images are 8-bit TIFF, sRGB, with the brightness and colours of the camera's JPEG. Running it again overwrites them.

### Stack One Angle

Give it the folder of one angle, or the whole `pictures` folder to merge every session at once:

```
./bin/stack.sh pictures/2026-10-07_12-13-58/angle_01_0.0deg
./bin/stack.sh pictures -o ~/stacked
```

When the folder itself is the stack, the image is named after it. When the stacks are deeper, the image is named after their path, e.g. `2026-10-07_12-13-58_angle_01_0.0deg.tif`.

## Parameters

`./bin/stack.sh` takes the same options as the `stack` command in the container. `./bin/stack.sh --help` lists them.

| Option | Default | Description |
|---|---|---|
| `-o`, `--output <dir>` | `<folder>/stacked` | Where to save the images. |
| `--jpg` | off | Save JPEG instead of TIFF. |
| `--depthmap` | off | Also save a depth map of each stack, `<name>_depthmap.png`. |
| `--no-align` | off | Merge the frames as they are, without aligning them. See [Alignment](#alignment). |
| `--brightness <f>` | computed | Brightness multiplier, the same for every frame. By default it is computed from the first frame of each stack. |
| `--no-camera-tone` | off | Keep a plain sRGB rendering instead of the look of the camera's JPEG. See [Brightness and Colours](#brightness-and-colours). |
| `--min-jump <n>` | `256` | The smallest difference, in raw units, for a pixel to count as defective. The 5D Mark II is 14-bit: about `1024` is black and `15600` is white. |
| `--no-defect-repair` | off | Keep the hot and dead pixels. |
| `--half` | off | Decode at half resolution, 4 times faster, for previews. |
| `--rotate <degrees>` | `0` | Turn every image clockwise by `0`, `90`, `180` or `270` degrees. The orientation the camera records is ignored: the images come out as the sensor sees them, landscape, turned by this. |
| `--threads <n>` | one per core | Number of worker threads. Fewer threads use less memory. |
| `-v`, `--verbose` | off | Print the details of each step, including the alignment of each frame. |

## How It Works

[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) explains how the stacker and the watcher are built, and why.

Each frame goes through these steps:

1. [LibRaw](https://www.libraw.org/) unpacks the raw sensor data, before demosaicing.
2. StepIt Stacker repairs the hot and dead pixels in the raw data, in [`src/defect_pixels.cc`](src/defect_pixels.cc).
3. LibRaw demosaics the frame into an 8-bit sRGB image, with the white balance of the camera, then StepIt Stacker gives it the tone curve of the camera's JPEG. The brightness and the tone curve are the same for every frame of a stack.
4. focus-stack aligns the frame to the previous one, correcting position, rotation, magnification, brightness and white balance.
5. focus-stack merges all the frames with a wavelet transform, keeping the sharpest detail at each point, then saves the image.

The frames are decoded while the previous ones are being aligned and merged.

### Hot and Dead Pixels

The repair happens on the raw data, before alignment. A defective pixel sits at the same place on the sensor, but alignment moves each frame differently, so a defect left in place would land at a different spot in each frame. The merge favours sharp, contrasted points, so it would keep them all, as a trail of coloured dots.

A pixel counts as defective when two things are true:

- It is much brighter or darker than all 8 nearest pixels of its colour. The threshold grows with the local contrast, so edges are left alone, and with the brightness, so photon noise in bright areas is left alone.
- The 4 pixels touching it, which have the other colours, are not raised with it. Real light passes through the lens, which spreads even a tiny glint onto them; a defect stands alone.

The second test matters in macro work. Some surfaces, such as the matte top of a chip, sparkle at the scale of a single pixel. Without that test, a frame of a chip had about 3,800 pixels repaired, almost all on the chip surface. With it, each frame of the test sessions has about 100 to 250 repairs. About 160 of those positions repeat across frames of different subjects, so nearly all of them are true defects of the sensor.

### Brightness and Colours

A plain sRGB rendering of the raw data looks darker than the shots: on the test session, the median level was 65 out of 255, against 91 in the camera's JPEG, and the white background reached only 214. The camera applies its own tone curve, the Picture Style, which lifts the mid-tones and brings the highlights to white. Viewers show that JPEG, which every CR2 file embeds at full size.

StepIt Stacker reproduces it. On the first frame of each stack, it compares its rendering with the embedded JPEG, at 1/16 of the size so the few pixels the camera crops differently do not matter. For each colour, it takes the median level of the JPEG at each level of its rendering, and that is the tone curve. The same curve applies to every frame of the stack, so the frames still match each other. With it, the merged image of the test session has a median of 87 and highlights at 247, against 91 and 245 in the camera's JPEG.

The brightness that goes into the curve is LibRaw's automatic brightness, the one that leaves the brightest 1% of pixels white, computed once on the first frame. Every frame of a stack must have the same brightness and the same curve: values computed for each frame would vary with its content, and the merge would show bands where it switches between frames. Different stacks, e.g. different angles, each get their own.

### Alignment

The frames need aligning even though the rig repeats its positions exactly. On a linear rail the camera moves toward the subject, so each frame is magnified more than the one before: about 1.5% per step on the test sessions, 6% over 5 frames, about 110 pixels at the edges. The light falling on the subject also drops by about 2 to 3% per step. Without alignment, every edge appears several times in the merged image.

Alignment crops the image to the area all the frames cover, so the merged image is a little smaller than a frame.

### The Watcher

The rig tells when a stack is complete; the watcher never guesses from the files. A folder that stops growing may only be waiting for its next shot, so watching the files cannot tell a finished stack from one in progress.

On the rig, the objective `FocusStack` of [StepIt Macro](https://github.com/kineticsystem/stepit-macro) runs the behavior `StackDone` after the last shot of each angle. The camera reports a picture only once it is saved, and the objective waits for that report, so every picture of the angle is on the rig's disk by then. `StackDone` does two things:

- It writes `stack.json` into the angle's folder: the shots, the angle and the files of the folder. It is written to a temporary file and renamed, so its presence says the stack is complete.
- It publishes the folder, e.g. `2026-10-07_12-29-19/angle_01_0.0deg`, on the latched topic `/focus_stack/stack_done`.

The watcher, [`watcher/stack_watcher.py`](watcher/stack_watcher.py), listens to that topic through the commander's rosbridge, `ws://stepit.local:9090`, the WebSocket that StepIt UI uses: the rig's DDS stays on its own computer. For each stack, in the order they come, one at a time:

1. It copies the folder with `rsync` over ssh, as `robot@stepit.local`, and checks that every file `stack.json` lists has arrived.
2. It runs the stacker on it, into a temporary folder, and moves the image into `stacked` once it is whole: a merge cut short leaves no image behind.

At every connection, also after the rig or this computer restarted, it catches up: it asks the rig over ssh for every `stack.json`, and merges each stack that has no image here yet, or an image older than its `stack.json`. A stack shot while this computer was off is merged when it comes back.

It runs in the same image as the stacker. It reads the ssh keys of `~/.ssh`, mounted read-only, and resolves `stepit.local` through the host's Avahi daemon, whose socket is mounted, as Docker containers cannot resolve `.local` names on their own.

## Troubleshooting

**The watcher logs `Connection to the rig` errors**. The rig is off, or its commander is not running: the watcher tries again every 10 seconds, and catches up once connected. Check that the page of the rig, on port 8070, opens.

**The watcher logs `Cannot list the finished stacks of the rig`**. ssh to the rig failed: the watcher needs a key that logs in as `robot@stepit.local` without a password. Check it from this computer with `ssh -o BatchMode=yes robot@stepit.local true`.

**`Iterations do not converge` and `findTransformECC`**. The alignment found nothing to lock onto: the frames show mostly blank background, or large overexposed areas. That stack is skipped and the others are still merged. Frame the subject so it fills more of the picture, or reduce the exposure. As a last resort, `--no-align` merges the stack, with doubled edges.

**Coloured dots remain in the image**. A hot pixel that is only slightly too bright is below the threshold. Lower it, e.g. `--min-jump 128`, and compare the result.

**The image is too dark or too bright**. The tone curve copies the camera's JPEG, so the image is as bright as the shots on the camera's screen. Change the brightness for the whole stack, e.g. `--brightness 1.5`. If the output says `No camera JPEG`, the raw file has no embedded JPEG and the image has a plain sRGB rendering, which is darker.

**The images are turned the wrong way, or some angles differ from others**. The stacker ignores the orientation the camera records, whose tilt sensor cannot tell which way is up when the camera points down, and turns every image by `--rotate` instead. Pick the angle once, e.g. `./bin/watcher.sh start -- --rotate 90`.

**The stacker crashes with a segmentation fault**. focus-stack's alignment failed on a frame, and the process crashed instead of reporting it. It happened when the frames of a stack had different orientations, which the stacker now prevents, and it may still happen on frames with little texture. That stack gets no image; the watcher goes on with the next.

**Edges look doubled**. The stack was merged with `--no-align`, or the alignment of a frame went wrong. Run with `--verbose` and look at the `transform` lines: the magnification of each frame should be about 1.5% less than the previous one, e.g. `0.985`, then `0.971`.

## Licences

StepIt Stacker is released under the MIT licence, see [`LICENSE`](LICENSE). The libraries it uses allow that:

| Library | Licence | Role |
|---|---|---|
| [focus-stack](https://github.com/PetteriAimonen/focus-stack) | MIT | Aligns and merges the frames. |
| [OpenCV](https://opencv.org/) | Apache 2.0 | Image processing, used by focus-stack. |
| [LibRaw](https://www.libraw.org/) | LGPL 2.1 or CDDL 1.0 | Decodes the raw files. It is linked dynamically. |

GPL tools such as enfuse and `align_image_stack` from Hugin are not used: they cannot be linked into MIT code.
