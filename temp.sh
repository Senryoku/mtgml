#!/usr/bin/env bash

set -e
#require_clean_work_tree

# Still use this for latest card data
export GS_PATH=gs://cubeartisan/exports/
export DATE=`gsutil ls -lh $GS_PATH\
    | sed 's/^ *//g'\
    | cut -f 6 -d " "\
    | head -n -2\
    | sort\
    | tail -n 1\
    | cut -d '/' -f 5\
    | cut -d '.' -f 1`



export FILENAME_BASE=draft_data_public.${1^^}

export GITHUB_SHA=`git rev-parse HEAD`
export TYPE=$1


export REPOSITORY=ghcr.io/senryoku
docker buildx build --platform linux/arm64/v8,linux/amd64 --tag $REPOSITORY/mtgml:$TYPE-$DATE --tag $REPOSITORY/mtgml:$TYPE-latest . -f .docker/Dockerfile.eval --push
