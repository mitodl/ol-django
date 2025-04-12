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

COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /uvx /bin/

RUN useradd -G ubuntu dev
USER dev
WORKDIR /home/dev

# ===================================================================
FROM base as uv
ARG PYTHON_VERSION=3.11

USER dev

RUN uv python install $PYTHON_VERSION

# the pants installer puts things in ~/cache/nce and it needs to be persistent
RUN mkdir -p .cache && chown dev:dev .cache

VOLUME /home/dev/.cache
WORKDIR /home/dev/src

# ===================================================================
FROM uv as release

USER dev

WORKDIR /home/dev
RUN mkdir -m 0750 .ssh
COPY --chown=dev:dev . /home/dev/src

WORKDIR /home/dev/src
RUN uv sync
