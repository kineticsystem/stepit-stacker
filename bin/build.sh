#!/bin/bash -e

# Builds the stacker into ./build. Run it inside the container, e.g.
# `docker exec <container-name> build.sh`: the libraries are installed there.

# Move to the repo root, so the script can be called from anywhere.
cd "$(dirname "$(readlink -f "$0")")/.."

if [[ ! -f modules/raw-converter/CMakeLists.txt ]]; then
    echo "modules/raw-converter is empty: run 'git submodule update --init' on the host" >&2
    exit 1
fi

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build --parallel
