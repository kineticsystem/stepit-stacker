#include "raw_loader.hh"

#include <libraw/libraw.h>

#include <algorithm>
#include <memory>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>
#include <stdexcept>
#include <vector>

namespace stack
{

namespace
{

void check(int status, const std::string& step, const std::string& path)
{
  if (status != LIBRAW_SUCCESS)
  {
    throw std::runtime_error(path + ": " + step + " failed: " + libraw_strerror(status));
  }
}

// The brightness multiplier that leaves the brightest 1% of pixels white, as
// LibRaw computes it when automatic brightness is on (see copy_mem_image() in
// LibRaw): there, the white level is the 99th percentile of each colour, in a
// histogram of the 16-bit values divided by 8, and the multiplier is 8192
// divided by the highest of them.
float autoBrightness(const LibRaw& raw)
{
  const auto& image = raw.imgdata.image;
  const size_t pixels = size_t(raw.imgdata.sizes.iwidth) * raw.imgdata.sizes.iheight;
  const int colors = raw.imgdata.idata.colors;
  std::vector<std::vector<size_t>> histogram(colors, std::vector<size_t>(0x2000, 0));
  for (size_t i = 0; i < pixels; ++i)
  {
    for (int c = 0; c < colors; ++c)
    {
      histogram[c][image[i][c] >> 3]++;
    }
  }
  const size_t brightest = size_t(pixels * raw.imgdata.params.auto_bright_thr);
  int white = 0;
  for (int c = 0; c < colors; ++c)
  {
    int level = 0x2000;
    size_t total = 0;
    while (--level > 32 && (total += histogram[c][level]) <= brightest) {}
    white = std::max(white, level);
  }
  return 8192.0f / white;
}

// Fits the tone curve that maps our rendering of a frame, bgr, to the camera's
// JPEG of the same frame. See RawImage::tone. flip is the orientation of the
// raw file.
cv::Mat fitCameraTone(LibRaw& raw, int flip, const cv::Mat& bgr)
{
  if (raw.unpack_thumb() != LIBRAW_SUCCESS || raw.imgdata.thumbnail.tformat != LIBRAW_THUMBNAIL_JPEG)
  {
    return {};
  }
  int status = LIBRAW_SUCCESS;
  std::unique_ptr<libraw_processed_image_t, void (*)(libraw_processed_image_t*)> thumb(
      raw.dcraw_make_mem_thumb(&status), LibRaw::dcraw_clear_mem);
  if (!thumb || status != LIBRAW_SUCCESS)
  {
    return {};
  }
  // The JPEG is stored as the sensor sees it; our rendering is turned upright.
  // Turn the JPEG with the orientation of the raw file, not with its own EXIF
  // orientation, which OpenCV would otherwise apply.
  cv::Mat camera = cv::imdecode(cv::Mat(1, int(thumb->data_size), CV_8U, thumb->data),
                                cv::IMREAD_COLOR | cv::IMREAD_IGNORE_ORIENTATION);
  switch (flip)
  {
    case 3:
      cv::rotate(camera, camera, cv::ROTATE_180);
      break;
    case 5:
      cv::rotate(camera, camera, cv::ROTATE_90_COUNTERCLOCKWISE);
      break;
    case 6:
      cv::rotate(camera, camera, cv::ROTATE_90_CLOCKWISE);
      break;
  }
  if (camera.empty() || (camera.cols > camera.rows) != (bgr.cols > bgr.rows))
  {
    return {};
  }

  // Compare the two at 1/16 of the size: the camera crops the sensor a few
  // pixels differently, which becomes less than a pixel there.
  const cv::Size size(bgr.cols / 16, bgr.rows / 16);
  cv::Mat ours, theirs;
  cv::resize(bgr, ours, size, 0, 0, cv::INTER_AREA);
  cv::resize(camera, theirs, size, 0, 0, cv::INTER_AREA);

  cv::Mat lut(1, 256, CV_8UC3);
  for (int c = 0; c < 3; ++c)
  {
    // The camera's levels found at each of our levels.
    std::vector<std::vector<uchar>> found(256);
    for (int y = 0; y < size.height; ++y)
    {
      for (int x = 0; x < size.width; ++x)
      {
        found[ours.at<cv::Vec3b>(y, x)[c]].push_back(theirs.at<cv::Vec3b>(y, x)[c]);
      }
    }
    // The median of each level seen often enough, then straight lines across
    // the levels in between, from black and to white.
    std::vector<std::pair<int, int>> points = { { 0, 0 } };
    for (int level = 1; level < 255; ++level)
    {
      auto& values = found[level];
      if (values.size() >= 8)
      {
        std::nth_element(values.begin(), values.begin() + values.size() / 2, values.end());
        points.emplace_back(level, values[values.size() / 2]);
      }
    }
    points.emplace_back(255, 255);
    int highest = 0;
    for (size_t i = 0; i + 1 < points.size(); ++i)
    {
      const auto [x0, y0] = points[i];
      const auto [x1, y1] = points[i + 1];
      for (int level = x0; level <= x1; ++level)
      {
        // Never darker than a lower level: noise must not invert the curve.
        highest = std::max(highest, y0 + (y1 - y0) * (level - x0) / std::max(1, x1 - x0));
        lut.at<cv::Vec3b>(0, level)[c] = uchar(highest);
      }
    }
  }
  return lut;
}

}  // namespace

RawImage loadRaw(const std::string& path, const RawOptions& options)
{
  // LibRaw is a large object: keep it off the stack.
  auto raw = std::make_unique<LibRaw>();
  auto& params = raw->imgdata.params;
  params.output_bps = 8;     // focus-stack merges 8-bit images.
  params.output_color = 1;   // sRGB.
  params.gamm[0] = 1 / 2.4;  // sRGB gamma curve.
  params.gamm[1] = 12.92;
  params.use_camera_wb = 1;   // The white balance set on the camera.
  params.no_auto_bright = 1;  // The brightness is set below, the same for every frame of a stack.
  params.half_size = options.half_size ? 1 : 0;

  check(raw->open_file(path.c_str()), "open", path);
  check(raw->unpack(), "unpack", path);
  RawImage result;
  if (options.repair_defects)
  {
    result.repaired = repairDefectPixels(*raw, options.min_jump);
  }
  check(raw->dcraw_process(), "processing", path);
  // LibRaw applies the brightness when it makes the 8-bit image, below.
  result.brightness = options.brightness == kAutoBrightness ? autoBrightness(*raw) : options.brightness;
  params.bright = result.brightness;

  const int flip = raw->imgdata.sizes.flip;
  int status = LIBRAW_SUCCESS;
  std::unique_ptr<libraw_processed_image_t, void (*)(libraw_processed_image_t*)> image(
      raw->dcraw_make_mem_image(&status), LibRaw::dcraw_clear_mem);
  check(status, "conversion", path);
  if (!image || image->type != LIBRAW_IMAGE_BITMAP || image->colors != 3 || image->bits != 8)
  {
    throw std::runtime_error(path + ": unexpected image format");
  }
  const cv::Mat rgb(image->height, image->width, CV_8UC3, image->data);
  cv::cvtColor(rgb, result.bgr, cv::COLOR_RGB2BGR);  // Copies, so the LibRaw buffer can be freed.

  if (options.camera_tone)
  {
    result.tone = options.tone.empty() ? fitCameraTone(*raw, flip, result.bgr) : options.tone;
    if (!result.tone.empty())
    {
      cv::LUT(result.bgr, result.tone, result.bgr);
    }
  }
  return result;
}

}  // namespace stack
