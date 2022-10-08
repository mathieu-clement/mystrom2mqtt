#!/bin/sh
set -eu

cd "$(dirname $0)"

# Add --push to push to docker hub at the same time

docker buildx build --platform linux/amd64 -t mathieuclement/mystrom2mqtt:latest --no-cache -f Dockerfile .
