#include "fuse.hh"

#include <opencv2/imgproc.hpp>

#include <algorithm>
#include <cmath>

namespace merge
{

namespace
{

// The pyramid stops when its residual would be smaller than this, in pixels.
constexpr int kSmallestResidual = 16;

const cv::Matx13f kLuminance(0.2627f, 0.6780f, 0.0593f);

int levelsFor(cv::Size size)
{
  const int smallest = std::min(size.width, size.height);
  return std::max(1, static_cast<int>(std::floor(std::log2(static_cast<double>(smallest) / kSmallestResidual))));
}

// The detail at each scale, then the residual last.
std::vector<cv::Mat> laplacianPyramid(const cv::Mat& image, int levels)
{
  std::vector<cv::Mat> pyramid;
  cv::Mat current = image;
  for (int level = 0; level < levels; ++level)
  {
    cv::Mat down, up;
    cv::pyrDown(current, down);
    cv::pyrUp(down, up, current.size());
    pyramid.push_back(current - up);
    current = down;
  }
  pyramid.push_back(current);
  return pyramid;
}

// The amount of detail around each point: the luminance of the detail, made
// positive and smoothed, so that one noisy pixel does not decide alone.
cv::Mat detailEnergy(const cv::Mat& detail)
{
  cv::Mat luminance, energy;
  cv::transform(detail, luminance, kLuminance);
  luminance = cv::abs(luminance);
  cv::GaussianBlur(luminance, energy, cv::Size(5, 5), 1.0);
  return energy;
}

}  // namespace

void PyramidFusion::add(const cv::Mat& rgb)
{
  CV_Assert(rgb.type() == CV_32FC3);
  std::vector<cv::Mat> pyramid =
      laplacianPyramid(rgb, count_ == 0 ? levelsFor(rgb.size()) : static_cast<int>(detail_.size()));
  cv::Mat residual = pyramid.back();
  pyramid.pop_back();

  if (count_ == 0)
  {
    detail_ = pyramid;
    for (const cv::Mat& detail : detail_)
    {
      energy_.push_back(detailEnergy(detail));
    }
    residual_sum_ = residual.clone();
  }
  else
  {
    for (size_t level = 0; level < detail_.size(); ++level)
    {
      const cv::Mat energy = detailEnergy(pyramid[level]);
      const cv::Mat sharper = energy > energy_[level];
      pyramid[level].copyTo(detail_[level], sharper);
      energy.copyTo(energy_[level], sharper);
    }
    residual_sum_ += residual;
  }
  ++count_;
}

cv::Mat PyramidFusion::result() const
{
  CV_Assert(count_ > 0);
  cv::Mat image = residual_sum_ / count_;
  for (int level = static_cast<int>(detail_.size()) - 1; level >= 0; --level)
  {
    cv::Mat up;
    cv::pyrUp(image, up, detail_[level].size());
    image = up + detail_[level];
  }
  return image;
}

}  // namespace merge
