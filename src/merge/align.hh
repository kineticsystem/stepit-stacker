// Aligns the frames of a focus stack. On the rig's rail the camera moves toward
// the subject, so each frame is shifted and magnified a little relative to the
// one before. Each frame is matched to its neighbour with an affine transform,
// and every frame is then mapped onto one reference frame: the most magnified
// one. It sees the smallest area, which every other frame covers, so the merged
// image has no empty borders, and as every angle of a session makes the same
// rail steps, every angle gets the same size and the same framing.

#pragma once

#include <opencv2/core.hpp>

#include <vector>

namespace merge
{

// The small grayscale image a frame is aligned with: its linear luminance at
// half the size, CV_32F.
cv::Mat alignmentImage(const cv::Mat& rgb);

struct Alignment
{
  int reference = 0;
  // For each frame, the 2x3 CV_64F affine transform from the reference's
  // pixel coordinates to the frame's, at full size.
  std::vector<cv::Mat> transforms;
  // For each frame, the factor that brings its brightness to the reference's:
  // the light on the subject changes a little from one rail position to the next.
  std::vector<double> gains;
};

// Takes the alignmentImage() of every frame, in the order they were shot.
// Throws std::runtime_error, naming the frame, when one cannot be aligned.
Alignment alignStack(const std::vector<cv::Mat>& images);

// The frame as the reference sees it: same size, same framing, same brightness.
cv::Mat toReference(const cv::Mat& rgb, const Alignment& alignment, int frame);

}  // namespace merge
