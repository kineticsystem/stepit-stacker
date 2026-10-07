# TODO

What StepIt Stacker still needs, written down as it came up while merging the rig's first sessions. The goal is a professional video made from the stacked images of a session, one image per angle of the stage, so the items that a video needs come first. Each item says what we measured, and the options we see.

## Table of Contents <!-- omit in toc -->

- [For a Video](#for-a-video)
  - [1. The Same Framing for Every Angle](#1-the-same-framing-for-every-angle)
  - [2. 16-bit Images for Grading](#2-16-bit-images-for-grading)
  - [3. The Light Flickers Between Angles](#3-the-light-flickers-between-angles)
- [Merging](#merging)
  - [4. A Failed Alignment Crashes the Stacker](#4-a-failed-alignment-crashes-the-stacker)
  - [5. One Tone Curve per Session](#5-one-tone-curve-per-session)
- [The Watcher](#the-watcher)
  - [6. A Failed Stack Is Never Retried](#6-a-failed-stack-is-never-retried)
  - [7. The Mirror Only Grows](#7-the-mirror-only-grows)
- [Quality](#quality)
  - [8. No Automated Tests](#8-no-automated-tests)
  - [9. The Defect Repair Was Measured at ISO 800 Only](#9-the-defect-repair-was-measured-at-iso-800-only)

## For a Video

### 1. The Same Framing for Every Angle

Every angle of a session must have the same size and the same framing, or the video jumps and changes scale from one frame to the next. Today it does not: alignment crops each stack to the area all its frames cover, and that area differs per stack. The session of 2026-10-07 13:19 gave:

| Angle | Size |
|---|---|
| −8° | 3482 × 5222 |
| −4° | 3521 × 5273 |
| 0° | 3518 × 5284 |
| 8° | 3508 × 5279 |

The magnification of the rail is the same at every angle, as the rail makes the same steps, so the frame every stack is aligned to has the same framing. Options:

- Keep the full size, `ALIGN_KEEP_SIZE` of focus-stack, and crop every image of the session to one fixed rectangle, e.g. the smallest area all the stacks cover, or a margin set once for the rig.
- Align every stack to the same frame of the rail, e.g. the first, so the framing is the one the rig shot at that step.

This comes first: without it, nothing else makes a usable video.

### 2. 16-bit Images for Grading

The images are 8-bit TIFF with the camera's tone curve: good to look at, but they leave little room to compress the tones or change the colours when grading the video. focus-stack aligns and merges in 8 bits per channel only, so 16-bit images need another merge:

1. **focus-stack for the alignment and the depth map, our own merge in 16 bits.** focus-stack tells how to align each frame and which frame is sharpest at each point; the 16-bit frames are then assembled from that. This is close to Zerene Stacker's depth map method, DMap: clean on smooth subjects, weaker than focus-stack's merge on fine detail that overlaps, e.g. hairs or fibres in front of each other.
2. **focus-stack's wavelet merge, ported to 16 bits in our code.** The same quality as today, but a larger job: its merge assumes 8 bits throughout.
3. **Ask the author of focus-stack** for 16-bit support, and wait.

The 16-bit image should be flat, without the camera's tone curve, so that the grading starts from neutral data, and in sRGB primaries, as the video. The 8-bit image with the camera's look can stay, for viewing.

**16-bit TIFF, not DNG.** A linear DNG would let darktable or RawTherapee, which open it on Linux, change the white balance as on a raw file. But the video tools, DaVinci Resolve, Kdenlive, Blender and ffmpeg, all take a sequence of 16-bit TIFF directly, while a linear DNG is not a camera's CinemaDNG, which Resolve may refuse, and would then need developing into TIFF first. The white balance and the exposure are set in the camera and the same in every file of a session, so the raw white balance of a DNG would rarely be needed. Lightroom does not run on Linux.

### 3. The Light Flickers Between Angles

In the session of 2026-10-07 13:31, the background of the images gets about 23% brighter from −8° to +8°, which a video shows as pulsing brightness. The stacker does not cause it: each image is within 1 to 3.5 levels of the camera's own JPEG of the same angle, and the camera's JPEGs show the same change, with the same ISO 400, 0.8 s, f/8 and white balance in every file. The light reaching the camera really changes: most likely the stage, and what the subject sits on, tilt toward the lights as they turn.

| Angle | Stacked image, background | Camera's JPEG, background |
|---|---|---|
| −8° | 184.4 | 180.9 |
| −4° | 185.8 | 184.7 |
| 0° | 193.8 | 193.2 |
| 4° | 210.3 | 206.8 |
| 8° | 224.9 | 222.5 |

Options:

- **On the rig**, the real cure: diffuse light, e.g. a diffuser or a light tent, or a background that does not turn with the stage.
- **In the stacker**: bring every angle to the brightness of a reference, e.g. by the level of the background. It also evens out real changes of light on the subject, and has to guess what the background is.
- **In the video**: the deflicker filter of DaVinci Resolve, in its Studio version.

## Merging

### 4. A Failed Alignment Crashes the Stacker

When focus-stack's alignment fails on a frame, the stacker dies with a segmentation fault instead of reporting an error, and the stack gets no image. On 2026-10-07, four angles failed this way. In the one whose files we could still check, the frames had different orientations, which the camera's tilt sensor recorded and the stacker followed; the stacker now ignores the camera's orientation, and the others most likely failed the same way. Frames with little texture, e.g. a subject at the edge of the frame on a plain background, may still make the alignment fail.

- Report the failure cleanly instead of crashing: detect focus-stack's failed task and stop the merge.
- Reuse the alignment of a good stack. Every angle of a session makes the same rail steps, so the transform from one frame to the next is nearly the same for all of them, mostly a zoom: 0.3% to 1.5% per step on the sessions measured. A stack that fails could be aligned with the transforms of another angle of the session.

### 5. One Tone Curve per Session

The brightness and the camera's tone curve are computed on the first frame of each stack, so each angle gets its own. In the session of 2026-10-07 13:31, the automatic brightness went from ×3.45 at −8° to ×1.00 at +8°. It makes no visible difference, as the tone curve maps each rendering onto the camera's JPEG and cancels it, see the table of item 3; but a curve fitted once per session, and saved with the session, would be exactly the same for every angle.

Found on the way: `--brightness` does nothing while the camera's tone curve is on, as the fit cancels it too. It should apply after the fit.

## The Watcher

### 6. A Failed Stack Is Never Retried

The watcher checks the rig for stacks without an image only when it connects. A stack whose merge failed stays without an image until the watcher restarts, and then fails again the same way. Once item 4 gives a way to merge it, the watcher could retry it after the other stacks of the session.

### 7. The Mirror Only Grows

The mirror keeps every raw file: about 300 MB per angle, about 10 GB for a session of 35 angles. Nothing removes them. A rule is needed, e.g. keep the raw files for a number of days, or remove them once the image is merged, depending on whether a session will ever be merged again from its raw files.

## Quality

### 8. No Automated Tests

Everything was checked by hand, see [Tests](docs/ARCHITECTURE.md#tests). A change to the thresholds of the defect repair, or to the tone curve, could make the images worse silently. Worth having:

- Unit tests of the defect repair, on a synthetic Bayer pattern with hot pixels and a glint, and of the tone curve.
- The test of the watcher that was run by hand, a fake rig folder with a stand-in `ssh` and an announcement through a rosbridge, as a script.
- A GitHub Actions workflow that builds the image and runs them.

### 9. The Defect Repair Was Measured at ISO 800 Only

Its thresholds were measured on the rig's 5D Mark II at ISO 800 and 0.8 s: 100 to 250 repairs per frame, of which about 160 positions repeat across frames of different subjects. Hot pixels and noise change with the ISO and the exposure: measure again, as [Tests](docs/ARCHITECTURE.md#tests) describes, before shooting at other settings.
