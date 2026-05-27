#!/usr/bin/env bash
set -euo pipefail
set +x

SRC_DIR="${AISTUDIO_SOURCE_DIR:-/mnt/c/Users/bamboo/Desktop/aistudio-api_u1}"
RUN_ROOT="${AISTUDIO_WARMUP_SMOKE_ROOT:-/home/bamboo/aistudio-api-warmup-smoke-$(date +%Y%m%d-%H%M%S)}"
PORT="${AISTUDIO_WARMUP_SMOKE_PORT:-18190}"
TASK_REL=".trellis/tasks/05-27-account-pool-startup-warmup"

mkdir -p "$RUN_ROOT"
rsync -a --delete \
  --exclude .git \
  --exclude .venv \
  --exclude venv \
  --exclude data \
  "$SRC_DIR/" "$RUN_ROOT/repo/"

cd "$RUN_ROOT/repo"
python3 -m venv venv
. venv/bin/activate
python -m pip install -q -e .
python -m playwright install firefox >/dev/null 2>&1 || true

export AISTUDIO_PORT="$PORT"
export AISTUDIO_ACCOUNTS_DIR="${AISTUDIO_ACCOUNTS_DIR:-/home/bamboo/aistudio-api/data/accounts}"
export AISTUDIO_ACCOUNT_WARMUP_LIMIT="${AISTUDIO_ACCOUNT_WARMUP_LIMIT:-2}"
export AISTUDIO_LOCAL_STUDIO_DIR="$RUN_ROOT/data/local-studio"
export AISTUDIO_REQUEST_LOGS_DIR="$RUN_ROOT/data/request-logs"
export AISTUDIO_GENERATED_IMAGES_DIR="$RUN_ROOT/data/generated-images"
export AISTUDIO_IMAGE_SESSIONS_DIR="$RUN_ROOT/data/image-sessions"
export SYSTEM_TEST_ARTIFACTS_DIR="$RUN_ROOT/artifacts"
export SERVER_LOG="$RUN_ROOT/artifacts/server.log"

mkdir -p "$SYSTEM_TEST_ARTIFACTS_DIR" "$AISTUDIO_LOCAL_STUDIO_DIR" "$AISTUDIO_REQUEST_LOGS_DIR" "$AISTUDIO_GENERATED_IMAGES_DIR" "$AISTUDIO_IMAGE_SESSIONS_DIR"

python main.py server --port "$PORT" >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!
cleanup() {
  if kill -0 "$SERVER_PID" >/dev/null 2>&1; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

python "$TASK_REL/verification/warmup_smoke.py" \
  --base-url "http://127.0.0.1:$PORT" \
  --server-log "$SERVER_LOG" \
  --artifacts-dir "$SYSTEM_TEST_ARTIFACTS_DIR"

echo "RUN_ROOT=$RUN_ROOT"
echo "SUMMARY=$SYSTEM_TEST_ARTIFACTS_DIR/summary.md"
echo "RESULTS=$SYSTEM_TEST_ARTIFACTS_DIR/results.json"