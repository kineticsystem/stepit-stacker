cmake_minimum_required(VERSION 3.22)

project(stepit_stacker LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

find_package(OpenCV REQUIRED COMPONENTS core imgproc imgcodecs video)
find_package(PkgConfig REQUIRED)
pkg_check_modules(LIBRAW REQUIRED IMPORTED_TARGET libraw_r)

# focus-stack (MIT) aligns and merges the frames. Its own CMakeLists.txt only
# works as the top-level project, so fetch the sources and build its library
# here, without its command line tool. The commit is pinned so that a rebuild
# never changes the result.
include(FetchContent)
FetchContent_Declare(
  focus_stack
  GIT_REPOSITORY https://github.com/PetteriAimonen/focus-stack.git
  GIT_TAG 0cd289e224fe24aead5b146faeaa46950775f346
  SOURCE_SUBDIR do-not-add-subdirectory)
FetchContent_MakeAvailable(focus_stack)

file(GLOB FOCUS_STACK_SOURCES ${focus_stack_SOURCE_DIR}/src/*.cc)
list(FILTER FOCUS_STACK_SOURCES EXCLUDE REGEX ".*(_tests|main)\\.cc$")
add_library(focus_stack STATIC ${FOCUS_STACK_SOURCES})
target_include_directories(focus_stack PUBLIC ${focus_stack_SOURCE_DIR}/src)
target_link_libraries(focus_stack PUBLIC ${OpenCV_LIBS})
# Third-party code: do not drown our own warnings in its.
target_compile_options(focus_stack PRIVATE -w)

add_executable(stack src/main.cc src/raw_loader.cc src/defect_pixels.cc)
target_compile_options(stack PRIVATE -Wall -Wextra)
target_link_libraries(stack PRIVATE focus_stack PkgConfig::LIBRAW)
