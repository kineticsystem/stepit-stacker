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
// Splitting a frame into its pyramid is the slow part, and frames can be split
// at the same time, with split(); they are then added one at a time, in the
// order they were shot, so the memory stays that of the pyramids being split
// and the merged one, whatever the number of frames.

#pragma once

#include <opencv2/core.hpp>

#include <vector>

namespace merge
{

// A frame split for the fusion: its detail at each scale, how much detail
// each point of it has, and its residual.
struct Layers
{
  std::vector<cv::Mat> detail;  // CV_32FC3.
  std::vector<cv::Mat> energy;  // CV_32F.
  cv::Mat residual;             // CV_32FC3.
};

class PyramidFusion
{
public:
  // Splits a frame, CV_32FC3, for add(). It touches no PyramidFusion, so
  // several frames can be split at the same time.
  static Layers split(const cv::Mat& rgb);
  // Adds a split frame. Every frame must have the size of the first.
  void add(Layers layers);
  // Splits and adds a frame, CV_32FC3.
  void add(const cv::Mat& rgb) { add(split(rgb)); }
  // The merged image, CV_32FC3.
  cv::Mat result() const;

private:
  std::vector<cv::Mat> detail_;  // The merged detail at each scale, CV_32FC3.
  std::vector<cv::Mat> energy_;  // How much detail the merged pixels have, CV_32F.
  cv::Mat residual_sum_;
  int count_ = 0;
};

}  // namespace merge
