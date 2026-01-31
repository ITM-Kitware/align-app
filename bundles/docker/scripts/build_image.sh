#!/usr/bin/env bash
CURRENT_DIR=$(dirname "$0")

cd "$CURRENT_DIR/../../.."
ROOT_DIR="$PWD"

docker build -t align-app -f bundles/docker/Dockerfile .
