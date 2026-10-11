# TODO

What StepIt Stacker still needs. The goal is a sequence of high-quality images, one per angle of the stage, graded by hand on one image and then the same way on all of them, and shown as a 3D image on the Looking Glass Portrait. The items that the sequence and the display need come first. Each item says what we know, and the options we see.

## Table of Contents <!-- omit in toc -->

- [For the Image Sequence](#for-the-image-sequence)
  - [1. Try the Pipeline on the Rig's Stacks](#1-try-the-pipeline-on-the-rigs-stacks)
  - [2. The Light Flickers Between Angles](#2-the-light-flickers-between-angles)
- [For the 3D Display](#for-the-3d-display)
  - [3. Fewer Angles Than Views](#3-fewer-angles-than-views)
- [Merging](#merging)
  - [4. An Angle Whose Alignment Fails Gets No Image](#4-an-angle-whose-alignment-fails-gets-no-image)
  - [5. The Hot Pixels Were Not Checked on the Rig's Frames](#5-the-hot-pixels-were-not-checked-on-the-rigs-frames)
- [The Watcher](#the-watcher)
  - [6. A Failed Angle Is Retried Only at the Next Connection](#6-a-failed-angle-is-retried-only-at-the-next-connection)
  - [7. The Mirror Only Grows](#7-the-mirror-only-grows)
- [Quality](#quality)
  - [8. Tests of the Watcher and the Display](#8-tests-of-the-watcher-and-the-display)
- [Grading](#grading)
  - [9. darktable's Editor Is Hard to Use](#9-darktables-editor-is-hard-to-use)

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

### 3. Fewer Angles Than Views

The quilt has 48 views, a session 35 angles. The pipeline makes the missing views between the angles with optical flow, warping the nearer angle, which can distort the subject where the flow fails, e.g. thin legs or hairs crossing each other; blending both angles showed ghosts there instead. Options:

- **Shoot 48 angles**: the clean way, at the price of a longer session.
- **A 7 × 5 quilt**, which Looking Glass's tools accept, at the price of larger jumps between views.

The view cone of the Portrait is about 58°, the rig's ±8° far less: the depth is smaller, not wrong.

## Merging

### 4. An Angle Whose Alignment Fails Gets No Image

`focus-merge` stops with `frame N cannot be aligned with frame N-1` when a pair of frames gives the alignment nothing to lock onto, e.g. a subject at the edge of the frame on a plain background. That angle gets no image, and the quilt has one angle less. Every angle makes the same rail steps, so the transform from one frame to the next is nearly the same for all of them, mostly a zoom: 0.3% to 1.5% per step on the sessions measured. An angle that fails could be aligned with the transforms of another angle of the session.

### 5. The Hot Pixels Were Not Checked on the Rig's Frames

raw-convert repairs them: those that stand out in each frame, in units of the frame's noise, and the camera's known defects of `config/defects.txt`, which is not made yet. On the rig's 5D Mark II at ISO 800 and 0.8 s, frames had 100 to 250 defective pixels, about 160 of them at the same positions across frames of different subjects; 10 frames at ISO 400 had 703 repaired. Make `config/defects.txt` from photos of several scenes (see the README), then check on a session, at 100%, that the frames have no bright pixel left, and that real detail is intact: the matte top of a chip sparkles at the scale of a single pixel, and must stay. raw-convert leaves alone what spreads over several pixels, e.g. glints.

## The Watcher

### 6. A Failed Angle Is Retried Only at the Next Connection

The watcher catches up on the angles without a graded image when it connects to the rig, and every minute, but the catch-up every minute leaves alone what failed. An angle that failed stays without an image until the watcher reconnects or restarts, and then fails again the same way. Once item 4 gives a way to merge it, the watcher could retry it after the other angles of the session.

### 7. The Mirror Only Grows

The mirror keeps every raw file, about 300 MB per angle, and each angle adds a merged and a graded image, about 100 MB each: about 17 GB for a session of 35 angles. Nothing removes them. A rule is needed, e.g. keep the raw files for a number of days, or remove them once the angle is merged, depending on whether a session will ever be merged again from its raw files. The merged images are the masters for grading again, and should stay.

## Quality

### 8. Tests of the Watcher and the Display

`./bin/pipeline.sh test` tests `focus-merge`, the quilt, the upload to StepIt Holo's server, and the watcher, against a fake rig. Worth having:

- A test of the watcher's link to the rig's topics: `test_rig.py` tests the copy over HTTP against a stand-in for StepIt Camera's web server, but the WebSocket is untested. The topics through a rosbridge, as a script.
- A test of the development and the grading on a real CR2 of the rig, in the repo.
- A GitHub Actions workflow that builds the image and runs them.

## Grading

### 9. darktable's Editor Is Hard to Use

The grading is made by hand in darktable's editor, `./bin/pipeline.sh edit`, and applied to every angle by `darktable-cli`. darktable is powerful but hard to use for a quick edit of exposure, highlights, shadows and colour temperature. An editor like Lightroom would do, as long as it saves its edit as a file that a command line tool applies, unchanged, to every merged image. The candidates:

| Editor | The edit, saved as | Applied by | To check |
|---|---|---|---|
| [RapidRAW](https://github.com/CyberTimon/RapidRAW) | `.rrdata` sidecar, or a JSON of adjustments | `rapidraw export --adjustments <file>`, headless, 16-bit TIFF | The closest to Lightroom. Does it read the merged image's ICC profile, linear Rec. 2020, or take it for sRGB? It renders on the GPU: does the headless export run in the container? A young project: pin its version. |
| [ART](https://github.com/artraweditor/ART) | `.arp` profile, plain text | `ART-cli -p <profile> -t16`, 16-bit TIFF | Simpler than RawTherapee, which it forks. Not in Ubuntu's packages: a pinned release in the image. |
| [RawTherapee](https://www.rawtherapee.com/) | `.pp3` profile, plain text | `rawtherapee-cli -p <profile> -t16`, 16-bit TIFF | In Ubuntu's packages. Its editor is closer to darktable's than to Lightroom's. |

The edit is made on the merged image of the angle closest to 0°, as now, not on a raw frame: the pipeline grades merged images, and a profile made on a raw file carries raw settings, e.g. its demosaicing and raw white balance, that do not apply to a TIFF. Keep to edits of the whole image: a mask stays in place while the subject turns.

To try one: open a `2_merged/*.tif` of a session in it, check that it looks as in darktable, save an edit, apply it with its command line tool in the container, and compare with the editor's own result. Then `pipeline/darktable.py`'s `grade()` and `edit()` get a counterpart for it, and `config/grade.xmp` its own default edit.
