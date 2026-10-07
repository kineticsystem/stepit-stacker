// Merges each focus stack of a folder into a single image, as Zerene Stacker
// does: decode the raw frames, align them and keep the sharpest detail of each.

#include <focusstack.hh>

#include <algorithm>
#include <cctype>
#include <filesystem>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <vector>

#include "raw_loader.hh"

namespace fs = std::filesystem;

namespace
{

struct Options
{
  fs::path input;
  fs::path output;  // Empty: <input>/stacked.
  bool jpeg = false;
  // Even with a rig that repeats its positions, the frames need aligning: on a
  // linear rail the camera moves towards the subject, so each frame is
  // magnified a little more than the one before, about 1.5% per step.
  bool align = true;
  bool depthmap = false;
  bool verbose = false;
  int threads = 0;  // 0: focus-stack's default, one per core.
  stack::RawOptions raw;
};

void printUsage(std::ostream& out)
{
  out << "Usage: stack <folder> [options]\n"
         "\n"
         "Merges each focus stack found in <folder> into one image. A stack is a\n"
         "folder of raw files (CR2, ...): <folder> itself, or any folder below it.\n"
         "\n"
         "Options:\n"
         "  -o, --output <dir>   Where to save the images (default: <folder>/stacked)\n"
         "  --jpg                Save JPEG instead of TIFF\n"
         "  --depthmap           Also save a depth map of each stack\n"
         "  --no-align           Merge the frames as they are, without aligning them\n"
         "  --brightness <f>     Brightness multiplier for every frame (default: computed\n"
         "                       from the first frame of each stack)\n"
         "  --no-camera-tone     Keep a plain sRGB rendering instead of the look of the\n"
         "                       camera's JPEG\n"
         "  --min-jump <n>       Defect repair threshold, in raw units (default: "
      << stack::kDefaultMinJump
      << ")\n"
         "  --no-defect-repair   Do not repair hot and dead pixels\n"
         "  --half               Decode at half resolution, for quick previews\n"
         "  --threads <n>        Number of worker threads (default: one per core)\n"
         "  -v, --verbose        Print the details of each step\n"
         "  -h, --help           Print this help\n";
}

// Returns false, after printing why, if the arguments are wrong.
bool parseArguments(int argc, char** argv, Options& options)
{
  std::vector<std::string> args(argv + 1, argv + argc);
  for (size_t i = 0; i < args.size(); ++i)
  {
    const std::string& arg = args[i];
    auto value = [&]() -> const std::string& {
      if (i + 1 >= args.size())
      {
        throw std::invalid_argument(arg + " needs a value");
      }
      return args[++i];
    };
    if (arg == "-h" || arg == "--help")
    {
      printUsage(std::cout);
      std::exit(0);
    }
    else if (arg == "-o" || arg == "--output")
    {
      options.output = value();
    }
    else if (arg == "--jpg")
    {
      options.jpeg = true;
    }
    else if (arg == "--no-align")
    {
      options.align = false;
    }
    else if (arg == "--depthmap")
    {
      options.depthmap = true;
    }
    else if (arg == "--brightness")
    {
      options.raw.brightness = std::stof(value());
    }
    else if (arg == "--min-jump")
    {
      options.raw.min_jump = std::stoi(value());
    }
    else if (arg == "--no-camera-tone")
    {
      options.raw.camera_tone = false;
    }
    else if (arg == "--no-defect-repair")
    {
      options.raw.repair_defects = false;
    }
    else if (arg == "--half")
    {
      options.raw.half_size = true;
    }
    else if (arg == "--threads")
    {
      options.threads = std::stoi(value());
    }
    else if (arg == "-v" || arg == "--verbose")
    {
      options.verbose = true;
    }
    else if (!arg.empty() && arg[0] == '-')
    {
      throw std::invalid_argument("unknown option " + arg);
    }
    else if (options.input.empty())
    {
      options.input = arg;
    }
    else
    {
      throw std::invalid_argument("only one folder can be given");
    }
  }
  if (options.input.empty())
  {
    throw std::invalid_argument("missing folder");
  }
  return true;
}

bool isRawFile(const fs::path& path)
{
  static const std::set<std::string> kExtensions = { ".cr2", ".cr3", ".crw", ".nef", ".arw", ".dng",
                                                     ".raf", ".orf", ".rw2", ".pef", ".srw" };
  std::string extension = path.extension().string();
  std::transform(extension.begin(), extension.end(), extension.begin(), [](unsigned char c) { return std::tolower(c); });
  return kExtensions.count(extension) > 0;
}

// Maps each folder holding raw files to those files, sorted by name, which is
// the order the camera took them in.
std::map<fs::path, std::vector<fs::path>> findStacks(const fs::path& root, const fs::path& skip)
{
  std::map<fs::path, std::vector<fs::path>> stacks;
  for (auto it = fs::recursive_directory_iterator(root); it != fs::recursive_directory_iterator(); ++it)
  {
    if (it->is_directory() && fs::equivalent(it->path(), skip))
    {
      it.disable_recursion_pending();
    }
    else if (it->is_regular_file() && isRawFile(it->path()))
    {
      stacks[it->path().parent_path()].push_back(it->path());
    }
  }
  for (auto& [folder, files] : stacks)
  {
    std::sort(files.begin(), files.end());
  }
  return stacks;
}

// The name of a stack's image: its path below the root, e.g.
// "angle_01_-17.0deg", or the root's own name when the root is the stack.
std::string stackName(const fs::path& folder, const fs::path& root)
{
  const fs::path relative = fs::relative(folder, root);
  if (relative == ".")
  {
    return fs::canonical(root).filename().string();
  }
  std::string name = relative.generic_string();
  std::replace(name.begin(), name.end(), '/', '_');
  return name;
}

bool mergeStack(const std::vector<fs::path>& files, const fs::path& output, const fs::path& depthmap,
                const Options& options)
{
  focusstack::FocusStack merger;
  merger.set_output(output.string());
  if (!depthmap.empty())
  {
    merger.set_depthmap(depthmap.string());
  }
  merger.set_verbose(options.verbose);
  if (!options.align)
  {
    merger.set_align_flags(focusstack::FocusStack::ALIGN_NONE);
  }
  if (options.threads > 0)
  {
    merger.set_threads(options.threads);
  }

  // Decode the frames while the workers already align and merge the previous ones.
  merger.start();
  // The brightness and the tone curve of the first frame apply to all of them.
  stack::RawOptions raw_options = options.raw;
  for (const fs::path& file : files)
  {
    const stack::RawImage image = stack::loadRaw(file.string(), raw_options);
    if (raw_options.brightness == stack::kAutoBrightness)
    {
      raw_options.brightness = image.brightness;
      std::cout << "  Brightness: " << image.brightness << "\n";
    }
    if (raw_options.camera_tone && raw_options.tone.empty())
    {
      if (image.tone.empty())
      {
        std::cout << "  No camera JPEG in " << file.filename().string() << ": plain sRGB rendering\n";
        raw_options.camera_tone = false;
      }
      raw_options.tone = image.tone;
    }
    if (options.verbose || image.repaired > 0)
    {
      std::cout << "  " << file.filename().string() << ": " << image.repaired << " defective pixels repaired\n";
    }
    merger.add_image(image.bgr);
  }
  merger.do_final_merge();

  bool success = false;
  std::string error;
  merger.wait_done(success, error);
  if (!success)
  {
    std::cerr << "Error: " << error << "\n";
  }
  return success;
}

}  // namespace

int main(int argc, char** argv)
{
  Options options;
  try
  {
    parseArguments(argc, argv, options);
  }
  catch (const std::exception& e)
  {
    std::cerr << "Error: " << e.what() << "\n";
    printUsage(std::cerr);
    return 2;
  }

  if (!fs::is_directory(options.input))
  {
    std::cerr << "Error: " << options.input << " is not a folder\n";
    return 2;
  }
  const fs::path output = options.output.empty() ? options.input / "stacked" : options.output;
  fs::create_directories(output);

  const auto stacks = findStacks(options.input, output);
  if (stacks.empty())
  {
    std::cerr << "Error: no raw files found in " << options.input << "\n";
    return 1;
  }

  int failures = 0;
  for (const auto& [folder, files] : stacks)
  {
    const std::string name = stackName(folder, options.input);
    const fs::path image = output / (name + (options.jpeg ? ".jpg" : ".tif"));
    const fs::path depthmap = options.depthmap ? output / (name + "_depthmap.png") : fs::path();
    std::cout << "Stacking " << files.size() << " frames of " << folder.string() << "\n";
    try
    {
      if (mergeStack(files, image, depthmap, options))
      {
        std::cout << "  -> " << image.string() << "\n";
      }
      else
      {
        ++failures;
      }
    }
    catch (const std::exception& e)
    {
      std::cerr << "Error: " << e.what() << "\n";
      ++failures;
    }
  }

  std::cout << stacks.size() - failures << " of " << stacks.size() << " stacks merged\n";
  return failures == 0 ? 0 : 1;
}
