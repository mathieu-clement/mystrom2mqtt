#!/bin/sh
set -eu

docker run \
    -e 'SWITCHES=A4CF12FA3802:192.168.0.25,C82B9627CD8A:192.168.0.26' \
    -e 'BROKER=192.168.0.2' \
    -e 'POLLING_PERIOD=10' \
    --rm \
    --name mystrom2mqtt \
    ghcr.io/mathieuclement/mystrom2mqtt:latest
