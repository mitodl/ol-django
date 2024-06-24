# syntax=docker/dockerfile:1
FROM ubuntu:latest as base

SHELL ["bash", "-l", "-c"]
ENV SHELL=/bin/bash

RUN ln -fs /usr/share/zoneinfo/UTC /etc/localtime
RUN <<EOT bash
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y curl git build-essential pkg-config gdb lcov pkg-config \
      libbz2-dev libffi-dev libgdbm-dev libgdbm-compat-dev liblzma-dev \
      libncurses5-dev libreadline6-dev libsqlite3-dev libssl-dev \
      lzma lzma-dev tk-dev uuid-dev zlib1g-dev
EOT

WORKDIR /tmp
COPY apt.txt /tmp/apt.txt
RUN xargs apt-get install -y <apt.txt

RUN useradd dev
USER dev
WORKDIR /home/dev

# ===================================================================
FROM base as pyenv

RUN curl https://pyenv.run | bash
RUN <<EOT bash
    echo 'export PYENV_ROOT="\$HOME/.pyenv"' >> ~/.bashrc
    echo 'command -v pyenv >/dev/null || export PATH="\$PYENV_ROOT/bin:\$PATH"' >> ~/.bashrc
    echo 'eval "\$(pyenv init -)"' >> ~/.bashrc
    echo 'export PYENV_ROOT="\$HOME/.pyenv"' >> ~/.profile
    echo 'command -v pyenv >/dev/null || export PATH="\$PYENV_ROOT/bin:\$PATH"' >> ~/.profile
    echo 'eval "\$(pyenv init -)"' >> ~/.profile
EOT

# ===================================================================
FROM pyenv as py38
RUN pyenv install 3.8

# ===================================================================
FROM pyenv as py39
RUN pyenv install 3.9

# ===================================================================
FROM pyenv as py310
RUN pyenv install 3.10

# ===================================================================
FROM pyenv as py311
RUN pyenv install 3.11

# ===================================================================
FROM pyenv as shell


RUN curl --proto '=https' --tlsv1.2 -fsSL https://static.pantsbuild.org/setup/get-pants.sh | bash
RUN <<EOT bash
    echo 'export PATH="$PATH:\$HOME/.local/bin"' >> ~/.bashrc
EOT

# the pants installer puts things in ~/cache/nce and it needs to be persistent
RUN mkdir -p .cache && chown dev:dev .cache

# these are all separate stages to make them build in parallel
COPY --from=py38 /home/dev/.pyenv/versions ./.pyenv/versions/
COPY --from=py39 /home/dev/.pyenv/versions ./.pyenv/versions/
COPY --from=py310 /home/dev/.pyenv/versions ./.pyenv/versions/
COPY --from=py311 /home/dev/.pyenv/versions ./.pyenv/versions/

VOLUME /home/dev/.cache
WORKDIR /home/dev/src
