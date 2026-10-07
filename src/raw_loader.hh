// Decodes raw files (CR2 and the other formats LibRaw reads) into images that
// focus-stack can merge.

#pragma once

#include <opencv2/core.hpp>

#include <string>

#include "defect_pixels.hh"

namespace stack
{

// Compute the brightness from the frame, as LibRaw does by default.
constexpr float kAutoBrightness = 0.0f;

struct RawOptions
{
  // Repair hot and dead photosites before demosaicing, see defect_pixels.hh.
  bool repair_defects = true;
  int min_jump = kDefaultMinJump;
  // Linear brightness multiplier; 0 to compute it from the frame, see
  // RawImage::brightness. Every frame of a stack must have the same: a
  // brightness computed for each frame would vary with its content, and the
  // merge would show bands where it switches between frames.
  float brightness = kAutoBrightness;
  // Give the frame the look of the camera's own JPEG, see RawImage::tone.
  bool camera_tone = true;
  // The tone curve to apply; empty to fit it to the frame. Like the
  // brightness, it must be the same for every frame of a stack.
  cv::Mat tone;
  // Decode at half the resolution: 4 times faster, for previews.
  bool half_size = false;
  // Turn every frame clockwise by this many degrees: 0, 90, 180 or 270. The
  // orientation the camera records is ignored: its tilt sensor cannot tell
  // which way is up when the camera points down at the subject, and gives
  // frames of one stack different orientations, which cannot be merged.
  int rotation = 0;
};

struct RawImage
{
  cv::Mat bgr;       // 8-bit BGR, sRGB colour space and gamma.
  int repaired = 0;  // Photosites repaired by repairDefectPixels().
  // The brightness multiplier used: the one of the options, or the one
  // computed from the frame, which leaves its brightest 1% of pixels white.
  float brightness = 1.0f;
  // The tone curve used, a 1x256 CV_8UC3 lookup table for cv::LUT(): the one
  // of the options, or the one fitted to the frame. The fitted curve maps each
  // level of our rendering to the level of the camera's JPEG embedded in the
  // raw file, which has the camera's brightness and contrast. Empty when the
  // camera tone is off or the raw file has no JPEG.
  cv::Mat tone;
};

// Throws std::runtime_error if the file cannot be decoded.
RawImage loadRaw(const std::string& path, const RawOptions& options);

}  // namespace stack
