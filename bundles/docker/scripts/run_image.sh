#!/usr/bin/env bash
PORT=${1:-9000}
docker run -it --rm --gpus all -p ${PORT}:80 align-app
