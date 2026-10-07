#! /bin/bash -e

# Use this script to create, start, stop and remove the docker container that
# builds and runs the stacker.
#
# The container itself is defined in docker-compose.yml. This script only adds
# what compose cannot express: the host uid/gid and the container name passed
# on the command line.

function display_usage() {
    echo -e "\nUsage: ./dock.sh <container-name> <command> [options]\n
    Commands:
    build   Build a container without starting it
            Usage: ./dock.sh container-name build
    start   Start the container and open an interactive terminal
            Usage: ./dock.sh container-name start
    stop    Stop the container
            Usage: ./dock.sh container-name stop
    clean   Stop the container and clean everything including images
            Usage: ./dock.sh container-name clean\n"
}

# Compose resolves the paths in docker-compose.yml against the directory that
# holds it, so every command has to run from there.
cd "$(dirname "$0")"

# Check for at least two arguments (container name and command).
if [ "$#" -lt 2 ]; then
    echo "Missing required arguments."
    display_usage
    exit 1
fi

name="$1"
command="$2"

# The container name doubles as the compose project name, so several
# differently named containers can coexist from this same compose file.
export CONTAINER_NAME="$name"
export COMPOSE_PROJECT_NAME="$name"

# Build args for the Dockerfile: a container user matching the host user.
export USER_UID=$(id -u)
export USER_GID=$(id -g)

case "$command" in
    build)
        # Rebuilds the layers that the Dockerfile changed since last time, so
        # there is no need to clean first.
        docker compose build
        docker compose create
        ;;
    start)
        docker compose up --detach
        echo "Opening interactive terminal into $name"
        docker exec -it $name bash
        ;;
    stop)
        docker compose stop
        ;;
    clean)
        docker compose down --rmi local --remove-orphans
        ;;
    *)
        echo "Unknown parameter: $command"
        display_usage
        ;;
esac
