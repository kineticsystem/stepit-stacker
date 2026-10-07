// Merges aligned frames into one image that is sharp everywhere, in floating
// point, so the 16 bits of the frames are kept.
//
// Each frame is split into a Laplacian pyramid: its detail at a series of
// scales, from the finest to the coarsest, plus a small blurred residual. At
// each scale and each point, the merged image keeps the detail of the frame
// that has the most there: the frame in focus at that point. The residuals,
// the overall brightness, are averaged. Rebuilding the image from the merged
// pyramid blends the frames without visible seams.
//
// Frames are added one at a time, so the memory stays that of two pyramids
// whatever the number of frames.

#pragma once

#include <opencv2/core.hpp>

#include <vector>

namespace merge
{

class PyramidFusion
{
public:
  // Adds a frame, CV_32FC3. Every frame must have the size of the first.
  void add(const cv::Mat& rgb);
  // The merged image, CV_32FC3.
  cv::Mat result() const;

private:
  std::vector<cv::Mat> detail_;  // The merged detail at each scale, CV_32FC3.
  std::vector<cv::Mat> energy_;  // How much detail the merged pixels have, CV_32F.
  cv::Mat residual_sum_;
  int count_ = 0;
};

}  // namespace merge
