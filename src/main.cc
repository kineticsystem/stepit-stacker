// focus-merge: merges the developed frames of one focus stack, 16-bit TIFF
// files, into one 16-bit TIFF that is sharp everywhere.
//
//   focus-merge -o merged.tif frame1.tif frame2.tif ...
//
// The frames are read once, at the same time, and kept in 16 bits until each
// is merged: about 130 MB per frame of a 5D Mark II.

#include <algorithm>
#include <chrono>
#include <iostream>
#include <string>
#include <utility>
#include <vector>

#include <opencv2/core.hpp>

#include "align.hh"
#include "fuse.hh"
#include "parallel.hh"
#include "tiff_io.hh"

namespace
{

struct Options
{
  std::string output;
  std::vector<std::string> frames;
  int rotation = 0;  // Clockwise, in degrees.
};

void printUsage(std::ostream& out)
{
  out << "Usage: focus-merge -o <merged.tif> <frame.tif>... [--rotate <degrees>]\n"
         "\n"
         "Aligns the frames of a focus stack, 16-bit RGB TIFF files in the order they\n"
         "were shot, and merges them into one 16-bit TIFF that is sharp everywhere,\n"
         "with the colour profile of the frames.\n"
         "\n"
         "  -o <file>            The merged image\n"
         "  --rotate <degrees>   Turn the merged image clockwise by 0, 90, 180 or 270\n"
         "  -h, --help           Print this help\n";
}

Options parseArguments(int argc, char** argv)
{
  Options options;
  for (int i = 1; i < argc; ++i)
  {
    const std::string arg = argv[i];
    auto value = [&]() -> std::string {
      if (i + 1 >= argc)
      {
        throw std::invalid_argument(arg + " needs a value");
      }
      return argv[++i];
    };
    if (arg == "-h" || arg == "--help")
    {
      printUsage(std::cout);
      std::exit(0);
    }
    else if (arg == "-o")
    {
      options.output = value();
    }
    else if (arg == "--rotate")
    {
      options.rotation = std::stoi(value());
      if (options.rotation % 90 != 0 || options.rotation < 0 || options.rotation > 270)
      {
        throw std::invalid_argument("--rotate takes 0, 90, 180 or 270");
      }
    }
    else if (!arg.empty() && arg[0] == '-')
    {
      throw std::invalid_argument("unknown option " + arg);
    }
    else
    {
      options.frames.push_back(arg);
    }
  }
  if (options.output.empty())
  {
    throw std::invalid_argument("missing -o <merged.tif>");
  }
  if (options.frames.empty())
  {
    throw std::invalid_argument("no frames given");
  }
  return options;
}

cv::Mat rotated(const cv::Mat& image, int degrees)
{
  cv::Mat result;
  switch (degrees)
  {
    case 90:
      cv::rotate(image, result, cv::ROTATE_90_CLOCKWISE);
      return result;
    case 180:
      cv::rotate(image, result, cv::ROTATE_180);
      return result;
    case 270:
      cv::rotate(image, result, cv::ROTATE_90_COUNTERCLOCKWISE);
      return result;
    default:
      return image;
  }
}

double secondsSince(std::chrono::steady_clock::time_point start)
{
  return std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
}

}  // namespace

int main(int argc, char** argv)
{
  Options options;
  try
  {
    options = parseArguments(argc, argv);
  }
  catch (const std::exception& e)
  {
    std::cerr << "Error: " << e.what() << "\n";
    printUsage(std::cerr);
    return 2;
  }

  try
  {
    const auto start = std::chrono::steady_clock::now();
    const int count = static_cast<int>(options.frames.size());
    std::vector<merge::Image> images(count);
    std::vector<cv::Mat> alignment_images(count);
    merge::parallelFor(count, [&](int i) {
      images[i] = merge::readTiff(options.frames[i]);
      alignment_images[i] = merge::alignmentImage(merge::toFloat(images[i].rgb));
    });
    std::cout << "Read " << count << " frames in " << secondsSince(start) << " s\n";
    for (int i = 1; i < count; ++i)
    {
      if (images[i].rgb.size() != images[0].rgb.size())
      {
        throw std::runtime_error(options.frames[i] + " does not have the size of the first frame");
      }
    }
    const merge::Alignment alignment = merge::alignStack(alignment_images);
    alignment_images.clear();
    std::cout << "Aligned " << options.frames.size() << " frames to frame " << alignment.reference + 1 << " in "
              << secondsSince(start) << " s\n";

    // A few frames are warped and split at the same time, then added in the
    // order they were shot: more at a time compete for the memory's bandwidth
    // rather than go faster, and each holds its pyramid, about 450 MB.
    constexpr int kFramesAtATime = 4;
    merge::PyramidFusion fusion;
    const std::vector<uint8_t> icc = images[alignment.reference].icc;
    for (int first = 0; first < count; first += kFramesAtATime)
    {
      const int batch = std::min(kFramesAtATime, count - first);
      std::vector<merge::Layers> layers(batch);
      merge::parallelFor(batch, [&](int k) {
        const int i = first + k;
        layers[k] = merge::PyramidFusion::split(merge::toReference(images[i].rgb, alignment, i));
        images[i].rgb.release();  // Split: its memory goes back.
      });
      for (merge::Layers& frame : layers)
      {
        fusion.add(std::move(frame));
      }
    }
    merge::writeTiff(options.output, rotated(fusion.result(), options.rotation), icc);
    std::cout << "Merged into " << options.output << " in " << secondsSince(start) << " s\n";
  }
  catch (const std::exception& e)
  {
    std::cerr << "Error: " << e.what() << "\n";
    return 1;
  }
  return 0;
}
