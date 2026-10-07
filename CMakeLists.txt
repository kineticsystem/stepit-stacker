cmake_minimum_required(VERSION 3.22)

project(stepit_stacker LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

find_package(OpenCV REQUIRED COMPONENTS core imgproc video)
find_package(PkgConfig REQUIRED)
pkg_check_modules(LIBTIFF REQUIRED IMPORTED_TARGET libtiff-4)

# focus-merge aligns and merges the developed frames of one angle, in 16 bits,
# see docs/ARCHITECTURE.md.
add_executable(focus-merge src/main.cc src/tiff_io.cc src/align.cc src/fuse.cc)
target_compile_options(focus-merge PRIVATE -Wall -Wextra)
target_link_libraries(focus-merge PRIVATE ${OpenCV_LIBS} PkgConfig::LIBTIFF)
