#include "align.hh"

#include <opencv2/imgproc.hpp>
#include <opencv2/video.hpp>

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>

namespace merge
{

namespace
{

// The alignment images are at half the size of the frames.
constexpr int kAlignmentScale = 2;
// The match is refined from a coarse size to the full size of the alignment
// images, halving the scale each time. The coarsest size keeps at least this
// many pixels on its short side, below which the match does not converge.
constexpr int kCoarsestSide = 128;

// Linear Rec.2020 luminance.
const cv::Matx13f kLuminance(0.2627f, 0.6780f, 0.0593f);

cv::Mat toMat3x3(const cv::Mat& affine)
{
  cv::Mat m = cv::Mat::eye(3, 3, CV_64F);
  affine.convertTo(m.rowRange(0, 2), CV_64F);
  return m;
}

// The same transform for images `factor` times larger. The pixel i of the
// smaller image covers the pixels factor * i to factor * i + factor - 1 of the
// larger, whose centre is at factor * i + (factor - 1) / 2.
cv::Mat scaled(const cv::Mat& affine, double factor)
{
  const double offset = (factor - 1.0) / 2.0;
  cv::Mat s = (cv::Mat_<double>(3, 3) << factor, 0, offset, 0, factor, offset, 0, 0, 1);
  cv::Mat result = s * toMat3x3(affine) * s.inv();
  return result.rowRange(0, 2).clone();
}

cv::Mat downscaled(const cv::Mat& image, int factor)
{
  cv::Mat small;
  cv::resize(image, small, cv::Size(image.cols / factor, image.rows / factor), 0, 0, cv::INTER_AREA);
  return small;
}

// The transform from the pixels of `previous` to those of `next`, found by
// maximising their correlation (OpenCV's ECC), from a coarse size to the full
// size of the alignment images. The square root brings out the texture of the
// shadows, which linear values leave dark.
cv::Mat matchNeighbours(const cv::Mat& previous, const cv::Mat& next, const cv::Mat& guess)
{
  cv::Mat a, b;
  cv::sqrt(previous, a);
  cv::sqrt(next, b);
  int coarsest = 1;
  while (std::min(a.cols, a.rows) / (coarsest * 2) >= kCoarsestSide)
  {
    coarsest *= 2;
  }
  cv::Mat warp = scaled(guess, 1.0 / coarsest);
  for (int factor = coarsest; factor >= 1; factor /= 2)
  {
    const cv::Mat small_a = factor > 1 ? downscaled(a, factor) : a;
    const cv::Mat small_b = factor > 1 ? downscaled(b, factor) : b;
    cv::Mat warp32;
    warp.convertTo(warp32, CV_32F);
    const cv::TermCriteria criteria(cv::TermCriteria::COUNT | cv::TermCriteria::EPS, 100, 1e-6);
    cv::findTransformECC(small_a, small_b, warp32, cv::MOTION_AFFINE, criteria, cv::noArray(), 5);
    warp32.convertTo(warp, CV_64F);
    if (factor > 1)
    {
      warp = scaled(warp, 2.0);
    }
  }
  return warp;
}

double magnification(const cv::Mat& m)
{
  return std::sqrt(std::abs(cv::determinant(m(cv::Rect(0, 0, 2, 2)))));
}

}  // namespace

cv::Mat alignmentImage(const cv::Mat& rgb)
{
  cv::Mat gray;
  cv::transform(rgb, gray, kLuminance);
  return downscaled(gray, kAlignmentScale);
}

Alignment alignStack(const std::vector<cv::Mat>& images)
{
  const int count = static_cast<int>(images.size());
  // to_first[i] maps the pixels of the first frame to those of frame i.
  std::vector<cv::Mat> to_first(count);
  to_first[0] = cv::Mat::eye(3, 3, CV_64F);
  cv::Mat guess = cv::Mat::eye(2, 3, CV_64F);
  for (int i = 1; i < count; ++i)
  {
    try
    {
      guess = matchNeighbours(images[i - 1], images[i], guess);
    }
    catch (const cv::Exception& e)
    {
      throw std::runtime_error("frame " + std::to_string(i + 1) + " cannot be aligned with frame " + std::to_string(i) +
                               ": " + e.msg);
    }
    to_first[i] = toMat3x3(guess) * to_first[i - 1];
  }

  Alignment alignment;
  for (int i = 1; i < count; ++i)
  {
    if (magnification(to_first[i]) > magnification(to_first[alignment.reference]))
    {
      alignment.reference = i;
    }
  }
  const cv::Mat reference_inverse = to_first[alignment.reference].inv();
  const cv::Mat& reference = images[alignment.reference];
  const double reference_mean = cv::mean(reference)[0];
  for (int i = 0; i < count; ++i)
  {
    const cv::Mat reference_to_frame = to_first[i] * reference_inverse;
    const cv::Mat small = reference_to_frame.rowRange(0, 2);
    alignment.transforms.push_back(scaled(small, kAlignmentScale));
    // Blur does not change the mean, so frames focused at different depths
    // still compare fairly.
    cv::Mat warped;
    cv::warpAffine(images[i], warped, small, reference.size(), cv::INTER_LINEAR | cv::WARP_INVERSE_MAP,
                   cv::BORDER_REFLECT);
    const double mean = cv::mean(warped)[0];
    alignment.gains.push_back(mean > 0 ? reference_mean / mean : 1.0);
  }
  return alignment;
}

cv::Mat toReference(const cv::Mat& rgb, const Alignment& alignment, int frame)
{
  const cv::Mat& transform = alignment.transforms[frame];
  const cv::Size size(rgb.cols, rgb.rows);
  cv::Mat warped;
  cv::warpAffine(rgb, warped, transform, size, cv::INTER_CUBIC | cv::WARP_INVERSE_MAP, cv::BORDER_REFLECT);
  return warped * alignment.gains[frame];
}

}  // namespace merge
