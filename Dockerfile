# syntax=docker/dockerfile:1@sha256:ecfaec9ed6d810b56388c508f4121597bfbba70d41a6dfeee4d8cad5f295fc32
FROM ubuntu:latest@sha256:3131b4cc82a783df6c9df078f86e01819a13594b865c2cad47bd1bca2b7063bb as base

SHELL ["bash", "-l", "-c"]
ENV SHELL=/bin/bash

RUN ln -fs /usr/share/zoneinfo/UTC /etc/localtime
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update &&\
    apt-get install -y curl git build-essential pkg-config gdb lcov pkg-config \
      libbz2-dev libffi-dev libgdbm-dev libgdbm-compat-dev liblzma-dev \
      libncurses5-dev libreadline6-dev libsqlite3-dev libssl-dev \
      lzma tk-dev uuid-dev zlib1g-dev &&\
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
