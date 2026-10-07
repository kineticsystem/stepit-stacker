// Reads and writes the 16-bit RGB TIFF files of the pipeline: the frames that
// darktable develops, and the merged image.

#pragma once

#include <opencv2/core.hpp>

#include <cstdint>
#include <string>
#include <vector>

namespace merge
{

struct Image
{
  cv::Mat rgb;               // CV_32FC3, channels R, G, B, values from 0 to 1.
  std::vector<uint8_t> icc;  // The ICC profile of the file; empty if it has none.
};

// Reads a 16-bit RGB TIFF. Throws std::runtime_error if it is anything else.
Image readTiff(const std::string& path);

// Writes a 16-bit RGB TIFF, compressed without loss, with the ICC profile if
// one is given. Values outside 0 to 1 are clipped.
void writeTiff(const std::string& path, const cv::Mat& rgb, const std::vector<uint8_t>& icc);

}  // namespace merge
