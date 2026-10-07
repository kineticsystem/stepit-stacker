# Ubuntu 24.04 with the build tools and the libraries of the stacker, for user
# "developer". The same image builds the stacker and runs it.

# Looking Glass Bridge, the service that drives the Looking Glass Portrait: its
# installer for Ubuntu, from Looking Glass's Linux archive, run in the image
# below. Installing it accepts Looking Glass Factory's terms of use:
# https://lookingglassfactory.com/terms
FROM ubuntu:24.04 AS bridge

ARG BRIDGE_VERSION=2.6.3
ARG BRIDGE_SHA256=11542239311ba4906f0cfa5b877aa58524d38879f82c65c53e0539bb27c3d075

RUN apt-get update && apt-get -y install ca-certificates curl unzip
RUN curl -fsSL -o /tmp/bridge.zip \
    https://dhtk4bwj5r21z.cloudfront.net/HoloPlayService/PublicLinks/${BRIDGE_VERSION}/LookingGlassBridge-${BRIDGE_VERSION}-Linux.zip \
 && echo "${BRIDGE_SHA256}  /tmp/bridge.zip" | sha256sum -c - \
 && unzip -q /tmp/bridge.zip LookingGlassBridge-${BRIDGE_VERSION}-Ubuntu.sh -d /tmp \
 && mkdir /installer \
 && mv /tmp/LookingGlassBridge-${BRIDGE_VERSION}-Ubuntu.sh /installer/LookingGlassBridge-Ubuntu.sh

# LKG-Toolkit, whose command line tool shows a quilt through Bridge, built as
# it is: its licence forbids modifying it. It targets .NET 7, which Ubuntu
# 24.04 no longer ships: the .NET 8 SDK still builds it, and `lkg-toolkit`
# runs it on the .NET 8 runtime.
FROM ubuntu:24.04 AS lkg-toolkit

ARG LKG_TOOLKIT_COMMIT=0b6209bfa83c8eda5dd862666d4af83bd9e1ec67

RUN apt-get update && apt-get -y install ca-certificates git dotnet-sdk-8.0
RUN git clone https://github.com/Looking-Glass/LKG-Toolkit /tmp/LKG-Toolkit \
 && git -C /tmp/LKG-Toolkit checkout ${LKG_TOOLKIT_COMMIT} \
 && dotnet publish /tmp/LKG-Toolkit/Toolkit-CLI/Toolkit-CLI.csproj \
    -c Release --self-contained false -o /opt/lkg-toolkit

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

# OpenCV aligns and merges the frames (focus-stack is built on it), LibRaw
# decodes the raw files.
RUN apt-get -y install libopencv-dev libraw-dev

# The 3D pipeline, pipeline/: darktable develops and grades, focus-merge reads
# and writes 16-bit TIFF with libtiff, and the quilt is made with OpenCV.
RUN apt-get -y install darktable libtiff-dev python3-opencv python3-numpy

# The watcher, watcher/stack_watcher.py: it follows the rig through its
# rosbridge, copies each finished stack with rsync over ssh, and resolves the
# rig's name, e.g. stepit.local, through the host's Avahi daemon, whose socket
# bin/watcher.sh mounts.
RUN apt-get -y install python3 python3-websocket rsync openssh-client libnss-mdns

# Looking Glass Bridge and LKG-Toolkit, see the stages above: the libraries
# Bridge needs, for its window, its tray icon and the Portrait's USB, which its
# installer would install with sudo, and the .NET runtime of the toolkit.
RUN apt-get -y install libegl1 libgl1 libgles2 libglu1-mesa libgl1-mesa-dri \
    libx11-6 libxext6 libxi6 libxrandr2 libxcb-shm0 libgtk-3-0t64 libfreetype6 \
    libayatana-appindicator3-1 libasound2t64 libcurl4t64 libusb-1.0-0 \
    dotnet-runtime-8.0
RUN mkdir /opt/LookingGlassBridge && chown developer:developer /opt/LookingGlassBridge \
 && ln -s /opt/LookingGlassBridge/LookingGlassBridge /usr/local/bin/LookingGlassBridge
COPY --from=lkg-toolkit /opt/lkg-toolkit /opt/lkg-toolkit
RUN printf '#!/bin/sh\nDOTNET_ROLL_FORWARD=Major exec /opt/lkg-toolkit/Toolkit-CLI "$@"\n' > /usr/local/bin/lkg-toolkit \
 && chmod +x /usr/local/bin/lkg-toolkit

CMD ["bash"]

USER developer

# Bridge's installer refuses to run as root. Its options accept the licence and
# skip the dependencies, installed above; it then asks whether to uninstall
# earlier versions, answered no, and whether to share its analytics, answered
# no. It ends by starting Bridge, which stops with this step.
RUN --mount=type=bind,from=bridge,source=/installer,target=/installer \
    printf 'n\n2\n' | bash /installer/LookingGlassBridge-Ubuntu.sh \
    --prefix=/opt/LookingGlassBridge --exclude-subdir --skip-license --skip-dependencies

ENV HOME=/home/developer

# The repo is bind-mounted at ~/ws (see docker-compose.yml), so ./bin lives at
# a fixed path inside the container. Putting it on the PATH here rather than in
# a bashrc means it also applies to non-interactive shells, e.g.
# `docker exec <container-name> build.sh`.
ENV PATH="/home/developer/ws/bin:/home/developer/ws/build:${PATH}"

WORKDIR /home/developer/ws
