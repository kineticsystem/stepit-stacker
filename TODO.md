# TODO

What StepIt Stacker still needs, written down as it came up while merging the rig's first sessions. The goal is a sequence of high-quality images, one per angle of the stage, graded by hand on one image and then the same way on all of them; a quilt made from them shows the 3D image on a Looking Glass Portrait, item 10. The items that the sequence needs come first. Each item says what we measured, and the options we see.

## Table of Contents <!-- omit in toc -->

- [For the Image Sequence](#for-the-image-sequence)
  - [1. The Same Framing for Every Angle](#1-the-same-framing-for-every-angle)
  - [2. darktable Develops and Grades, the Stacker Merges in 16 Bits](#2-darktable-develops-and-grades-the-stacker-merges-in-16-bits)
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
- [The 3D Display](#the-3d-display)
  - [10. Show the Session on the Looking Glass Portrait](#10-show-the-session-on-the-looking-glass-portrait)

## For the Image Sequence

### 1. The Same Framing for Every Angle

Every angle of a session must have the same size and the same framing, or the sequence, and its preview video, jumps and changes scale from one angle to the next. Today it does not: alignment crops each stack to the area all its frames cover, and that area differs per stack. The session of 2026-10-07 13:19 gave:

| Angle | Size |
|---|---|
| −8° | 3482 × 5222 |
| −4° | 3521 × 5273 |
| 0° | 3518 × 5284 |
| 8° | 3508 × 5279 |

The magnification of the rail is the same at every angle, as the rail makes the same steps, so the frame every stack is aligned to has the same framing. Options:

- Keep the full size, `ALIGN_KEEP_SIZE` of focus-stack, and crop every image of the session to one fixed rectangle, e.g. the smallest area all the stacks cover, or a margin set once for the rig.
- Align every stack to the same frame of the rail, e.g. the first, so the framing is the one the rig shot at that step.

This comes first: without it, nothing else makes a usable sequence.

### 2. darktable Develops and Grades, the Stacker Merges in 16 Bits

A prototype does this, see [`pipeline/README.md`](pipeline/README.md): `config/develop.xmp`, a 16-bit merge of our own, `focus-merge`, and `grade.xmp`. Still to try on the rig's own stacks.

The images are 8-bit TIFF with the camera's tone curve, in sRGB: good to look at, but the tone curve has already compressed the highlights and the shadows, sRGB has clipped the most saturated colours, and 8 bits leave little room to move the highlights, the shadows, the mid-tones, the contrast or the saturation before banding shows. darktable takes over the development of the raw files and the grading, with two XMP files, and the stacker keeps only the alignment and the merge, in 16 bits:

1. **Develop each frame: `develop.xmp`, made once and kept in the repo.** `darktable-cli frame.cr2 develop.xmp frame.tif` turns every CR2 of a stack into a frame to merge. It makes no choice that needs looking at an image, so it is made once in darktable on any CR2 of the rig, and is the same for every stack and every session:
   - the hot pixels module, the demosaic, e.g. RCD or AMaZE, and the white balance the camera recorded;
   - no exposure, no tone mapping, filmic and sigmoid off, so the frame is **linear** and nothing clips;
   - output in **linear Rec.2020**, a wide gamut, with the ICC profile embedded: sRGB would clip the saturated colours before the grading could bring them back;
   - **16 bits per channel**: the 5D Mark II records 14 bits, 16 hold all of them;
   - nothing that changes the detail of a frame: no sharpening, no local contrast, no tone equalizer, no lens correction. The merge keeps, at each point, the frame with the most fine detail; sharpening boosts the noise in the blurred parts of a frame and draws halos along out-of-focus edges, either of which the merge can take for detail.

   The XMP must set each of these explicitly: without one, `darktable-cli` applies its own defaults, which include a tone mapping and +0.7 EV, and it may switch on sharpening for raw files.
2. **Merge the frames in 16 bits.** focus-stack aligns and merges in 8 bits per channel only, so the 16-bit frames need another merge:
   1. **focus-stack for the alignment and the depth map, our own merge in 16 bits.** focus-stack tells how to align each frame and which frame is sharpest at each point; the 16-bit frames are then assembled from that. This is close to Zerene Stacker's depth map method, DMap: clean on smooth subjects, weaker than focus-stack's merge on fine detail that overlaps, e.g. hairs or fibres in front of each other.
   2. **focus-stack's wavelet merge, ported to 16 bits in our code.** The same quality as today, but a larger job: its merge assumes 8 bits throughout.
   3. **Ask the author of focus-stack** for 16-bit support, and wait.
3. **Grade the merged image: `grade.xmp`, made by hand on the first image of a session.** Open the merged TIFF in darktable and grade it: the exposure, the tone equalizer for the shadows and the highlights, filmic or sigmoid for the contrast and how the highlights roll off, color balance rgb for the saturation and the colour of each tone range, then the sharpening, e.g. the lens deblur presets of diffuse or sharpen, and the lens and chromatic aberration corrections if they improve it. They come here because the merged image is sharp everywhere, and once instead of on every frame. darktable saves it as `image.tif.xmp`; the XMP is saved with the session, and the watcher runs `darktable-cli image.tif grade.xmp out.tif` on every merged image of the session as it arrives. A later session, or another subject, starts from it and adjusts it on its own first image; darktable can also keep a grading as a named style, for `darktable-cli --style`.

Edits drawn at one place of the image, e.g. a mask or a spot repair, land at the same place in every image while the subject turns: `grade.xmp` should keep to edits of the whole image. Changing the grading never needs a new merge: `grade.xmp` runs again on the merged images.

To install and check:

- `darktable` in the Docker image. The XMP files are made by the darktable of the desktop and read by the one of the image; a newer darktable may write module versions an older one cannot read, so both should be the same version. Ubuntu 24.04 ships 4.6.
- The 16-bit output of `darktable-cli`, which writes 8-bit TIFF unless told otherwise, e.g. `--core --conf plugins/imageio/format/tiff/bpp=16`.
- darktable's hot pixels module against the stacker's defect repair, on the same frames. Ours also repairs glints, which darktable's module, made for single pixels, may leave; and its threshold needs measuring at the rig's ISO and exposures, as item 9 says of ours.
- The time: every frame now goes through darktable, about 5 per angle and 35 angles per session.

Until then, the current development, LibRaw with our defect repair and the camera's tone curve, stays, and items 5 and 9 are about it. Its 8-bit image with the camera's look can stay for viewing, or darktable can make it from the graded image.

**16-bit TIFF between the steps, not DNG.** A linear DNG of the merged image would let darktable change the white balance again, as on a raw file. But `develop.xmp` already starts from the raw files, the white balance and the exposure are set in the camera and the same in every file of a session, and writing a DNG means writing its colour tags ourselves.

**ComfyUI was considered and left out.** It is made for image generation models: its own nodes read a 16-bit colour TIFF as 8 bits and save 8-bit PNG, and it has few grading tools. It could come after the grading, e.g. for upscaling.

### 3. The Light Flickers Between Angles

In the session of 2026-10-07 13:31, the background of the images gets about 23% brighter from −8° to +8°, which the sequence shows as pulsing brightness. A grading recipe applied the same way to every image keeps it. The stacker does not cause it: each image is within 1 to 3.5 levels of the camera's own JPEG of the same angle, and the camera's JPEGs show the same change, with the same ISO 400, 0.8 s, f/8 and white balance in every file. The light reaching the camera really changes: most likely the stage, and what the subject sits on, tilt toward the lights as they turn.

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
- **In the grading**: a different exposure per image, which defeats a recipe applied the same way to all of them.

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

## The 3D Display

### 10. Show the Session on the Looking Glass Portrait

A prototype does this, see [`pipeline/README.md`](pipeline/README.md): it builds the quilt, retiming the angles to 48 views, and shows it through Bridge. Still to try with the Portrait attached.

The end of a session should be a 3D image on the Looking Glass Portrait, with nobody at the PC: the rig shoots, the PC merges and grades every angle, then builds a quilt and shows it. The rig is left alone; the Portrait plugs into the PC, over HDMI for the image and USB-C for its calibration.

The Portrait needs no driver: Linux sees a plain 1536 × 2048 portrait monitor. The 3D comes from a lenticular sheet on the panel, and from software that rearranges a quilt into the pixels under each lens, in a fragment shader, with the calibration of that unit: its pitch, slope and center, in `LKG_calibration/visual.json` on a small drive the Portrait exposes over USB.

**The quilt.** For the Portrait: 8 columns × 6 rows, 48 views, 3360 × 3360, each view 420 × 560, aspect 0.75. View 0, the leftmost, is at the bottom left, and the rightmost at the top right. The file name tells the tools its layout, e.g. `session_qs8x6a0.75.png`. Building it is a few steps after the last angle of a session: crop every graded image to 3:4 with the same rectangle, which needs item 1, scale it to 420 × 560, and place it. The node `LookingGlassQuilt`, "Looking Glass Quilt 🪟", of [ComfyUI-LenticularPack](https://github.com/kineticsystem/ComfyUI-LenticularPack) already places the views this way, and names the file; the same few lines can run in the watcher, without ComfyUI. Two things to settle:

- **The number of views.** A session has 35 angles, the quilt 48. Options: shoot 48 angles; a 7 × 5 quilt, which the tools accept, at the price of larger jumps between views; or views made between the angles. The node `OpticalFlowRetimer`, "Optical Flow Retimer 🎬", of the same pack does the last: it turns any number of images into any other, warping the two neighbours of each new view toward it with OpenCV's Farneback optical flow, both ways, and blending them. On views of 420 × 560 it is quick, and the 8 bits it works in do not matter for the preview. Where the flow fails, e.g. thin legs or hairs crossing each other, a made view can show ghosts: shooting 48 angles stays the clean way.
- **The direction of the angles.** The Portrait shows parallax from left to right only, and the stage turns from right to left: the angles may need reversing so that view 0 is the leftmost.

The view cone of the Portrait is about 58°, the rig's ±8° far less: the depth is smaller, not wrong. The flicker of item 3 shows as a shimmer when the head moves.

**Showing it.** Looking Glass Bridge, the service that drives the display, and [LKG-Toolkit](https://github.com/Looking-Glass/LKG-Toolkit), whose command line shows a quilt through it, are in the Docker image. Neither is open source: Bridge comes under Looking Glass Factory's terms, LKG-Toolkit under its licence agreement.

- Bridge 2.6.3, installed into `/opt/LookingGlassBridge` by its own installer from its Linux archive, with its analytics off. It is supported on Ubuntu 22.04 only, but runs in the image, on Ubuntu 24.04: started on a virtual screen, it answers on its port, 33334.
- LKG-Toolkit, at a fixed commit, built unmodified, as its licence forbids changing it, for the .NET 7 it targets, and run on the .NET 8 runtime, as Ubuntu 24.04 no longer ships .NET 7, as `lkg-toolkit`. It connects to Bridge and lists its displays: none, as no Portrait was attached.

Showing a quilt should then be:

```bash
LookingGlassBridge &
lkg-toolkit -t play -i session_qs8x6a0.75.png -c 8 -r 6 -v 48 -q 0.75 --loop
```

The aspect is `-q`, not the `--aspect` of the toolkit's README. To check with the Portrait attached:

- The container sees the Portrait: the X socket of the host, `/tmp/.X11-unix` and `DISPLAY`, as Bridge draws through X, which Ubuntu 26.04 gives through XWayland; the GPU, `/dev/dri`; the USB of the Portrait, for Bridge's HID access, and its drive with `visual.json`. None of this is in `docker-compose.yml` yet.
- Bridge finds the Portrait, `lkg-toolkit -t list`, and draws on it, at 100% scaling, in portrait orientation, as Looking Glass asks.
- The quilt looks right: the order of the views, and the angles reversed if the depth looks inside out.

If Bridge does not work in the end, our own viewer can replace it: a fullscreen window on the Portrait's output, the calibration read from `visual.json`, and the lenticular shader that Looking Glass publishes, [HoloPlayShaders](https://docs.lookingglassfactory.com/core/core-sdk/index-1/holoplayshaders); the [surf-visualization scripts](https://github.com/surf-visualization/looking-glass) already make the native image from a quilt in Python. A few hundred lines of Python and OpenGL, but tuned by eye on the display. The Portrait's standalone mode, without a PC, plays only what Looking Glass Studio synced to it, and Studio has no Linux version.

The Portrait shows 420 × 560 per view: it is a preview of the session. The graded 16-bit images stay the result.
