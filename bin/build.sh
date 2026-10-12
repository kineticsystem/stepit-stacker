#!/bin/bash -e

# Builds the stacker into ./build. Run it inside the container, e.g.
# `docker exec <container-name> build.sh`: the libraries are installed there.

# Move to the repo root, so the script can be called from anywhere.
cd "$(dirname "$(readlink -f "$0")")/.."

for module in raw-converter stepit-grader; do
    if [[ ! -f "modules/$module/CMakeLists.txt" ]]; then
        echo "modules/$module is empty: run 'git submodule update --init --recursive' on the host" >&2
        exit 1
    fi
done

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build --parallel
