# syntax=docker/dockerfile:1@sha256:2780b5c3bab67f1f76c781860de469442999ed1a0d7992a5efdf2cffc0e3d769
FROM ubuntu:latest@sha256:c4a8d5503dfb2a3eb8ab5f807da5bc69a85730fb49b5cfca2330194ebcc41c7b as base

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

COPY --from=ghcr.io/astral-sh/uv:0.11.2@sha256:c4f5de312ee66d46810635ffc5df34a1973ba753e7241ce3a08ef979ddd7bea5 /uv /uvx /bin/

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
