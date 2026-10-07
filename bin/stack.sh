#!/bin/bash -e

# Merges the focus stacks of a folder, from the host: runs the stacker in a
# throwaway container of the stack image. Takes the same arguments as the
# stacker; run `stack.sh --help` to list them.
#
#   ./bin/stack.sh pictures/2026-10-07_12-29-19
#
# The first run builds the image and the stacker, which takes a few minutes.

repo="$(dirname "$(readlink -f "$0")")/.."
repo="$(readlink -f "$repo")"
image="${STACK_IMAGE:-stepit-stacker}"

if [[ -z $(docker images -q "$image:latest") ]]; then
    "$repo/docker/dock.sh" "$image" build
fi

# The repo goes where the dev container has it, so the CMake cache in ./build
# stays valid for both.
volumes=(-v "$repo:/home/developer/ws")

if [[ ! -x "$repo/build/stack" ]]; then
    docker run --rm "${volumes[@]}" "$image:latest" build.sh
fi

# The folders are mounted at their host paths, so they are given to the
# stacker as they are. The home holds the pictures and the working directory
# most of the time; any other folder is mounted on its own.
volumes+=(-v "$HOME:$HOME")
function mount_outside_home() {
    local path="$1"
    if [[ "$path" != "$HOME" && "$path" != "$HOME"/* ]]; then
        volumes+=(-v "$path:$path")
    fi
}

args=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        -o|--output)
            mkdir -p "$2"
            args+=("$1" "$(readlink -f "$2")")
            mount_outside_home "$(readlink -f "$2")"
            shift 2
            ;;
        -*)
            args+=("$1")
            shift
            ;;
        *)
            if [[ -e "$1" ]]; then
                args+=("$(readlink -f "$1")")
                mount_outside_home "$(readlink -f "$1")"
            else
                args+=("$1")  # A value of an option, e.g. --threads 4.
            fi
            shift
            ;;
    esac
done

exec docker run --rm --init "${volumes[@]}" -w /home/developer/ws "$image:latest" stack "${args[@]}"
