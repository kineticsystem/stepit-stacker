#include "tiff_io.hh"

#include <tiffio.h>

#include <memory>
#include <stdexcept>

namespace merge
{

namespace
{

using TiffFile = std::unique_ptr<TIFF, decltype(&TIFFClose)>;

TiffFile open(const std::string& path, const char* mode)
{
  TiffFile tif(TIFFOpen(path.c_str(), mode), &TIFFClose);
  if (!tif)
  {
    throw std::runtime_error("cannot open " + path);
  }
  return tif;
}

}  // namespace

Image readTiff(const std::string& path)
{
  TiffFile tif = open(path, "r");
  uint32_t width = 0, height = 0;
  uint16_t bits = 0, samples = 0, planar = PLANARCONFIG_CONTIG;
  TIFFGetField(tif.get(), TIFFTAG_IMAGEWIDTH, &width);
  TIFFGetField(tif.get(), TIFFTAG_IMAGELENGTH, &height);
  TIFFGetFieldDefaulted(tif.get(), TIFFTAG_BITSPERSAMPLE, &bits);
  TIFFGetFieldDefaulted(tif.get(), TIFFTAG_SAMPLESPERPIXEL, &samples);
  TIFFGetFieldDefaulted(tif.get(), TIFFTAG_PLANARCONFIG, &planar);
  if (bits != 16 || samples < 3 || planar != PLANARCONFIG_CONTIG)
  {
    throw std::runtime_error(path + " is not a 16-bit RGB TIFF");
  }

  // One row of the file, then its first 3 samples of each pixel: an alpha
  // channel, if any, is dropped.
  cv::Mat row(1, static_cast<int>(width), CV_16UC(samples));
  cv::Mat rgb16(static_cast<int>(height), static_cast<int>(width), CV_16UC3);
  for (uint32_t y = 0; y < height; ++y)
  {
    if (TIFFReadScanline(tif.get(), row.data, y) < 0)
    {
      throw std::runtime_error("cannot read " + path);
    }
    const uint16_t* in = row.ptr<uint16_t>();
    uint16_t* out = rgb16.ptr<uint16_t>(static_cast<int>(y));
    for (uint32_t x = 0; x < width; ++x)
    {
      for (int c = 0; c < 3; ++c)
      {
        out[x * 3 + c] = in[x * samples + c];
      }
    }
  }

  Image image;
  rgb16.convertTo(image.rgb, CV_32FC3, 1.0 / 65535.0);
  uint32_t icc_size = 0;
  void* icc_data = nullptr;
  if (TIFFGetField(tif.get(), TIFFTAG_ICCPROFILE, &icc_size, &icc_data) && icc_size > 0)
  {
    const auto* begin = static_cast<const uint8_t*>(icc_data);
    image.icc.assign(begin, begin + icc_size);
  }
  return image;
}

void writeTiff(const std::string& path, const cv::Mat& rgb, const std::vector<uint8_t>& icc)
{
  CV_Assert(rgb.type() == CV_32FC3);
  cv::Mat rgb16;
  rgb.convertTo(rgb16, CV_16UC3, 65535.0);  // Saturates below 0 and above 1.

  TiffFile tif = open(path, "w");
  TIFFSetField(tif.get(), TIFFTAG_IMAGEWIDTH, static_cast<uint32_t>(rgb16.cols));
  TIFFSetField(tif.get(), TIFFTAG_IMAGELENGTH, static_cast<uint32_t>(rgb16.rows));
  TIFFSetField(tif.get(), TIFFTAG_BITSPERSAMPLE, 16);
  TIFFSetField(tif.get(), TIFFTAG_SAMPLESPERPIXEL, 3);
  TIFFSetField(tif.get(), TIFFTAG_PHOTOMETRIC, PHOTOMETRIC_RGB);
  TIFFSetField(tif.get(), TIFFTAG_PLANARCONFIG, PLANARCONFIG_CONTIG);
  TIFFSetField(tif.get(), TIFFTAG_ORIENTATION, ORIENTATION_TOPLEFT);
  TIFFSetField(tif.get(), TIFFTAG_COMPRESSION, COMPRESSION_ADOBE_DEFLATE);
  TIFFSetField(tif.get(), TIFFTAG_PREDICTOR, PREDICTOR_HORIZONTAL);
  TIFFSetField(tif.get(), TIFFTAG_ROWSPERSTRIP, TIFFDefaultStripSize(tif.get(), 0));
  if (!icc.empty())
  {
    TIFFSetField(tif.get(), TIFFTAG_ICCPROFILE, static_cast<uint32_t>(icc.size()), icc.data());
  }
  for (int y = 0; y < rgb16.rows; ++y)
  {
    if (TIFFWriteScanline(tif.get(), rgb16.ptr(y), static_cast<uint32_t>(y)) < 0)
    {
      throw std::runtime_error("cannot write " + path);
    }
  }
}

}  // namespace merge
