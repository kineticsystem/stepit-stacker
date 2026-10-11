# Ubuntu 24.04 with the build tools, darktable and the libraries of the
# pipeline, for user "developer". The same image builds raw-convert and
# focus-merge, and runs the pipeline.

FROM ubuntu:24.04

LABEL name="develop:stepit-stacker"

RUN apt-get update

RUN apt-get -y install sudo
RUN echo 'root:docker' | chpasswd                      # Update user root password.

# Ubuntu 24.04 base images ship a default 'ubuntu' user at uid/gid 1000. Remove
# it so 'developer' can be created with a matching uid/gid to the host user
# (passed in via build args), which keeps the bind-mounted workspace writable.
RUN if id -u ubuntu >/dev/null 2>&1; then userdel -r ubuntu; fi
RUN if getent group ubuntu >/dev/null 2>&1; then groupdel ubuntu; fi

ARG USER_UID=1000
ARG USER_GID=1000

# Create the user developer with a uid/gid matching the host user so files
# created in the bind-mounted workspace and the stacked pictures are owned by
# the host user.
RUN groupadd -g ${USER_GID} developer
RUN useradd --create-home --shell /bin/bash --uid ${USER_UID} --gid ${USER_GID} developer
RUN echo 'developer:developer' | chpasswd              # Update user developer password.
RUN usermod -aG sudo developer                         # Add user to sudoers.
RUN echo 'developer ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/developer \
 && chmod 0440 /etc/sudoers.d/developer

RUN apt-get -y upgrade
RUN apt-get -y install build-essential cmake git ca-certificates pkg-config
RUN apt-get -y install clang-format

# raw-convert, of modules/raw-converter, develops with LibRaw and Little CMS;
# focus-merge aligns and merges with OpenCV and reads and writes the 16-bit
# TIFFs with libtiff; darktable grades, and the quilt is made with OpenCV for
# Python. Each layer updates the package lists itself: those of the first layer,
# cached, can name packages the archive has replaced since.
RUN apt-get update && apt-get -y install libraw-dev liblcms2-dev
RUN apt-get update && apt-get -y install darktable libopencv-dev libtiff-dev python3-opencv python3-numpy

# The watcher, pipeline/watch.py: it follows the rig through its rosbridge,
# copies each finished angle over HTTP, from StepIt Camera's web server, and
# resolves the rig's name, e.g. stepit.local, through the host's Avahi daemon,
# whose socket bin/pipeline.sh mounts.
RUN apt-get -y install python3 python3-websocket libnss-mdns

CMD ["bash"]

USER developer

ENV HOME=/home/developer

# The repo is bind-mounted at ~/ws (see docker-compose.yml), so ./bin lives at
# a fixed path inside the container. Putting it on the PATH here rather than in
# a bashrc means it also applies to non-interactive shells, e.g.
# `docker exec <container-name> build.sh`.
ENV PATH="/home/developer/ws/bin:/home/developer/ws/build:${PATH}"

WORKDIR /home/developer/ws
