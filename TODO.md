# TODO

What StepIt Stacker still needs. The goal is a sequence of high-quality images, one per angle of the stage, graded by hand on one image and then the same way on all of them, and shown as a 3D image on the Looking Glass Portrait. The items that the sequence and the display need come first. Each item says what we know, and the options we see.

## Table of Contents <!-- omit in toc -->

- [For the Image Sequence](#for-the-image-sequence)
  - [1. Try the Pipeline on the Rig's Stacks](#1-try-the-pipeline-on-the-rigs-stacks)
  - [2. The Light Flickers Between Angles](#2-the-light-flickers-between-angles)
- [For the 3D Display](#for-the-3d-display)
  - [3. Try the Portrait](#3-try-the-portrait)
  - [4. Fewer Angles Than Views](#4-fewer-angles-than-views)
- [Merging](#merging)
  - [5. An Angle Whose Alignment Fails Gets No Image](#5-an-angle-whose-alignment-fails-gets-no-image)
  - [6. The Hot Pixels Were Not Checked on the Rig's Frames](#6-the-hot-pixels-were-not-checked-on-the-rigs-frames)
- [The Watcher](#the-watcher)
  - [7. A Failed Angle Is Retried Only at the Next Connection](#7-a-failed-angle-is-retried-only-at-the-next-connection)
  - [8. The Mirror Only Grows](#8-the-mirror-only-grows)
- [Quality](#quality)
  - [9. Tests of the Watcher and the Display](#9-tests-of-the-watcher-and-the-display)

## For the Image Sequence

### 1. Try the Pipeline on the Rig's Stacks

The pipeline was tested on a session made of copies of one 5D Mark II raw file, and `focus-merge` on synthetic stacks. On the rig's own stacks, check:

- **The alignment**, on frames with real depth, and on subjects with little texture.
- **The framing**: every angle aligned to its most magnified frame should give every angle the same size and framing, as the rail makes the same steps at every angle.
- **The merge** on fine detail that overlaps, e.g. hairs or fibres in front of each other, where a Laplacian pyramid merge can come out less clean than a wavelet merge.
- **The time** of an angle of 5 or more frames: an angle of 3 frames takes about 20 seconds.
- **`images.rotate`** for the rig's camera.

### 2. The Light Flickers Between Angles

In the session of 2026-10-07 13:31, the background gets about 23% brighter from −8° to +8°, which the sequence shows as pulsing brightness, and the Portrait as a shimmer when the head moves. A grading applied the same way to every image keeps it. The camera's own JPEGs show the same change, with the same ISO 400, 0.8 s, f/8 and white balance in every file: the light reaching the camera really changes, most likely as the stage, and what the subject sits on, tilt toward the lights as they turn.

| Angle | Camera's JPEG, background |
|---|---|
| −8° | 180.9 |
| −4° | 184.7 |
| 0° | 193.2 |
| 4° | 206.8 |
| 8° | 222.5 |

Options:

- **On the rig**, the real cure: diffuse light, e.g. a diffuser or a light tent, or a background that does not turn with the stage.
- **In the pipeline**: bring every merged image to the brightness of a reference, e.g. by the level of the background, before the grading. It also evens out real changes of light on the subject, and has to guess what the background is.

## For the 3D Display

### 3. Try the Portrait

The display was tested without a Portrait: Bridge, in the container, took a quilt and played it. With the Portrait attached, check:

- **Bridge finds the Portrait** from the container: `./bin/pipeline.sh logs` warns `Bridge lists no Looking Glass display` if not. Bridge may need the Portrait's HID device, `/dev/hidraw*`, which only root can open by default: a udev rule on the host, made from the Portrait's USB ids in `lsusb`, gives it to the user. It may also need the Portrait's drive, with `LKG_calibration/visual.json`, which the container sees under `/media`.
- **Bridge draws on the Portrait** through XWayland, in portrait orientation, at 100% scaling.
- **The depth** is the right way: the stage turns from right to left, so `quilt.reverse` may be needed.

If Bridge does not work, our own viewer can replace it: a fullscreen window on the Portrait's output, the calibration read from `visual.json`, and the lenticular shader that Looking Glass publishes, [HoloPlayShaders](https://docs.lookingglassfactory.com/core/core-sdk/index-1/holoplayshaders); the [surf-visualization scripts](https://github.com/surf-visualization/looking-glass) already make the native image from a quilt in Python. A few hundred lines of Python and OpenGL, tuned by eye on the display. Check the licence of the shader first.

### 4. Fewer Angles Than Views

The quilt has 48 views, a session 35 angles. The pipeline makes the missing views between the angles with optical flow, which can show ghosts where the flow fails, e.g. thin legs or hairs crossing each other. Options:

- **Shoot 48 angles**: the clean way, at the price of a longer session.
- **A 7 × 5 quilt**, which Looking Glass's tools accept, at the price of larger jumps between views.

The view cone of the Portrait is about 58°, the rig's ±8° far less: the depth is smaller, not wrong.

## Merging

### 5. An Angle Whose Alignment Fails Gets No Image

`focus-merge` stops with `frame N cannot be aligned with frame N-1` when a pair of frames gives the alignment nothing to lock onto, e.g. a subject at the edge of the frame on a plain background. That angle gets no image, and the quilt has one angle less. Every angle makes the same rail steps, so the transform from one frame to the next is nearly the same for all of them, mostly a zoom: 0.3% to 1.5% per step on the sessions measured. An angle that fails could be aligned with the transforms of another angle of the session.

### 6. The Hot Pixels Were Not Checked on the Rig's Frames

darktable's hot pixels module repairs them with its default threshold and strength, in `config/develop.xmp`. On the rig's 5D Mark II at ISO 800 and 0.8 s, frames had 100 to 250 defective pixels, about 160 of them at the same positions across frames of different subjects. Check that the module repairs them, at the rig's ISO and exposures, without eating real detail: the matte top of a chip sparkles at the scale of a single pixel, and must stay. darktable's module works on single pixels, and may leave glints, small specular highlights spread over a few pixels.

## The Watcher

### 7. A Failed Angle Is Retried Only at the Next Connection

The watcher catches up on the angles without a graded image only when it connects to the rig. An angle that failed stays without an image until the watcher reconnects or restarts, and then fails again the same way. Once item 5 gives a way to merge it, the watcher could retry it after the other angles of the session.

### 8. The Mirror Only Grows

The mirror keeps every raw file, about 300 MB per angle, and each angle adds a merged and a graded image, about 100 MB each: about 17 GB for a session of 35 angles. Nothing removes them. A rule is needed, e.g. keep the raw files for a number of days, or remove them once the angle is merged, depending on whether a session will ever be merged again from its raw files. The merged images are the masters for grading again, and should stay.

## Quality

### 9. Tests of the Watcher and the Display

`./bin/pipeline.sh test` tests `focus-merge` and the quilt. Worth having:

- A test of the watcher: a fake rig, a folder with a stand-in `ssh` and `rsync`, and the topics through a rosbridge, as a script.
- A test of the development and the grading on a real CR2 of the rig, in the repo.
- A GitHub Actions workflow that builds the image and runs them.
