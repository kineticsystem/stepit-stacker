#include "fuse.hh"

#include <opencv2/imgproc.hpp>

#include <algorithm>
#include <cmath>
#include <utility>

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

Layers PyramidFusion::split(const cv::Mat& rgb)
{
  CV_Assert(rgb.type() == CV_32FC3);
  Layers layers;
  layers.detail = laplacianPyramid(rgb, levelsFor(rgb.size()));
  layers.residual = layers.detail.back();
  layers.detail.pop_back();
  for (const cv::Mat& detail : layers.detail)
  {
    layers.energy.push_back(detailEnergy(detail));
  }
  return layers;
}

void PyramidFusion::add(Layers layers)
{
  if (count_ == 0)
  {
    detail_ = std::move(layers.detail);
    energy_ = std::move(layers.energy);
    residual_sum_ = layers.residual.clone();
  }
  else
  {
    CV_Assert(layers.detail.size() == detail_.size());
    for (size_t level = 0; level < detail_.size(); ++level)
    {
      const cv::Mat sharper = layers.energy[level] > energy_[level];
      layers.detail[level].copyTo(detail_[level], sharper);
      layers.energy[level].copyTo(energy_[level], sharper);
    }
    residual_sum_ += layers.residual;
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
