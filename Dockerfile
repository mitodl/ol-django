# syntax=docker/dockerfile:1
FROM ubuntu:latest as base

SHELL ["bash", "-l", "-c"]
ENV SHELL=/bin/bash

RUN ln -fs /usr/share/zoneinfo/UTC /etc/localtime
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update &&\
    apt-get install -y curl git build-essential pkg-config gdb lcov pkg-config \
      libbz2-dev libffi-dev libgdbm-dev libgdbm-compat-dev liblzma-dev \
      libncurses5-dev libreadline6-dev libsqlite3-dev libssl-dev \
      lzma lzma-dev tk-dev uuid-dev zlib1g-dev &&\
    apt-get clean

WORKDIR /tmp
COPY apt.txt /tmp/apt.txt
RUN xargs apt-get install -y <apt.txt

RUN useradd dev
USER dev
WORKDIR /home/dev

# ===================================================================
FROM base as rye
ARG PYTHON_VERSION=3.11
ENV PATH="${PATH}:/home/dev/.rye/shims"
RUN curl -sSf https://rye.astral.sh/get | RYE_INSTALL_OPTION="--yes" bash &&\
    rye pin ${PYTHON_VERSION}

# ===================================================================

# the pants installer puts things in ~/cache/nce and it needs to be persistent
RUN mkdir -p .cache && chown dev:dev .cache


VOLUME /home/dev/.cache
WORKDIR /home/dev/src
