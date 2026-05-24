#!/usr/bin/env bash
set -euo pipefail

RUN_ROOT="/home/bamboo/aistudio-api-system-test-$(date +%Y%m%d-%H%M%S)"
REPO_SRC="/mnt/c/Users/bamboo/Desktop/aistudio-api_u1/"
REPO_DST="$RUN_ROOT/repo/"

mkdir -p "$RUN_ROOT"
rsync -a --delete --exclude .git --exclude .venv --exclude venv "$REPO_SRC" "$REPO_DST"

cd "$REPO_DST"
python3 -m venv venv
. venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
python -m playwright install firefox

mkdir -p \
  "$RUN_ROOT/data/local-studio" \
  "$RUN_ROOT/data/request-logs" \
  "$RUN_ROOT/data/generated-images" \
  "$RUN_ROOT/data/image-sessions" \
  "$RUN_ROOT/artifacts/screenshots"

printf 'RUN_ROOT=%s\n' "$RUN_ROOT"
