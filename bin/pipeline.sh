#!/bin/bash -e

# Runs the pipeline, pipeline/, in its container, stepit-pipeline. See README.md.
#
#   ./bin/pipeline.sh start                    build, then start the container and its watcher
#   ./bin/pipeline.sh stop
#   ./bin/pipeline.sh logs                     follow the watcher
#   ./bin/pipeline.sh session <session>        process a session folder, then show its quilt
#   ./bin/pipeline.sh grade <session>          grade it again, then show it
#   ./bin/pipeline.sh quilt <session>          build its quilt again, then show it
#   ./bin/pipeline.sh show <quilt.png>
#   ./bin/pipeline.sh test                     run the tests

repo="$(readlink -f "$(dirname "$(readlink -f "$0")")/..")"
image="${STACK_IMAGE:-stepit-stacker}"
name="stepit-pipeline"

function start() {
    # The raw-converter and stepit-grader modules, which a plain clone leaves empty.
    git -C "$repo" submodule update --init --recursive
    # Builds the layers of the Dockerfile that changed, if any, then the programs.
    "$repo/docker/dock.sh" "$image" build > /dev/null
    docker run --rm -v "$repo:/home/developer/ws" "$image:latest" build.sh > /dev/null

    # The repo where the dev container has it, the home at its own path for the
    # pictures, and the host's Avahi daemon to resolve the rig's .local name.
    local options=(
        -v "$repo:/home/developer/ws"
        -v "$HOME:$HOME"
        -v /run/avahi-daemon/socket:/run/avahi-daemon/socket
    )
    docker rm --force "$name" &> /dev/null || true
    docker run --detach --name "$name" --init "${options[@]}" -w /home/developer/ws "$image:latest" \
        python3 -u -m pipeline watch > /dev/null
    echo "The pipeline runs: ./bin/pipeline.sh logs to follow it"
}

function require_running() {
    if [[ "$(docker inspect -f '{{.State.Running}}' "$name" 2> /dev/null)" != "true" ]]; then
        echo "The pipeline is not running: ./bin/pipeline.sh start"
        exit 1
    fi
}

# A terminal for the commands when there is one, e.g. to stop them with Ctrl+C.
terminal=(-i)
if [[ -t 0 ]]; then terminal+=(-t); fi

command="$1"
shift || true
case "$command" in
    start)
        start
        ;;
    stop)
        docker rm --force "$name" > /dev/null
        echo "The pipeline is stopped"
        ;;
    logs)
        docker logs --follow --tail 50 "$name"
        ;;
    session|grade|quilt|show)
        require_running
        # The home is mounted at its own path, so a folder is given by its full path.
        path="$(readlink -f "$1")"
        shift
        docker exec "${terminal[@]}" -w /home/developer/ws "$name" python3 -m pipeline "$command" "$path" "$@"
        ;;
    test)
        require_running
        docker exec "${terminal[@]}" -w /home/developer/ws "$name" python3 -m unittest discover -v tests
        ;;
    *)
        sed -n '3,12p' "$0" | sed 's/^# \{0,1\}//'
        exit 2
        ;;
esac
