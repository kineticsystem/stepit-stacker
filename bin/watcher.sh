#!/bin/bash -e

# Runs the watcher, watcher/stack_watcher.py, in the background: it merges each
# focus stack of the rig as soon as the rig has shot it, into a mirror of the
# rig's pictures folder here. Docker starts it again with the computer, until
# it is stopped.
#
#   ./bin/watcher.sh start [-- <stacker options>]
#   ./bin/watcher.sh stop
#   ./bin/watcher.sh logs
#
# STACK_MIRROR sets the mirror (default: the folder pictures of this repo), STACK_RIG
# the rig (default: stepit.local).

repo="$(readlink -f "$(dirname "$(readlink -f "$0")")/..")"
image="${STACK_IMAGE:-stepit-stacker}"
name="stepit-stacker-watcher"
mirror="$(readlink -f "${STACK_MIRROR:-$repo/pictures}")"
rig="${STACK_RIG:-stepit.local}"

case "$1" in
    start)
        shift
        [[ "$1" == "--" ]] && shift
        # Builds the layers of the Dockerfile that changed, if any.
        "$repo/docker/dock.sh" "$image" build > /dev/null
        if [[ ! -x "$repo/build/stack" ]]; then
            docker run --rm -v "$repo:/home/developer/ws" "$image:latest" build.sh
        fi
        mkdir -p "$mirror"
        docker rm --force "$name" &> /dev/null || true
        # The repo where the dev container has it, the home at its own path
        # for the mirror, the ssh keys for rsync, and the host's Avahi daemon
        # to resolve the rig's .local name.
        docker run --detach --name "$name" --restart unless-stopped --init \
            -v "$repo:/home/developer/ws" \
            -v "$HOME:$HOME" \
            -v "$HOME/.ssh:/home/developer/.ssh:ro" \
            -v /run/avahi-daemon/socket:/run/avahi-daemon/socket \
            "$image:latest" \
            python3 -u /home/developer/ws/watcher/stack_watcher.py --rig "$rig" --mirror "$mirror" -- "$@" > /dev/null
        echo "The watcher runs: ./bin/watcher.sh logs to follow it"
        ;;
    stop)
        docker rm --force "$name" > /dev/null
        echo "The watcher is stopped"
        ;;
    logs)
        docker logs --follow --tail 50 "$name"
        ;;
    *)
        echo "Usage: ./bin/watcher.sh start [-- <stacker options>] | stop | logs"
        exit 2
        ;;
esac
