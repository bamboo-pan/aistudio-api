#!/usr/bin/env bash
set -euo pipefail
set +x

SRC_DIR="${AISTUDIO_SOURCE_DIR:-/mnt/c/Users/bamboo/Desktop/aistudio-api_u1}"
RUN_ROOT="${AISTUDIO_SYSTEM_TEST_RUN_ROOT:-/home/bamboo/aistudio-api-system-test-$(date +%Y%m%d-%H%M%S)}"
PORT="${AISTUDIO_SYSTEM_TEST_PORT:-18080}"
TASK_REL=".trellis/tasks/05-24-local-studio-real-system-test-plan"

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
export AISTUDIO_LOCAL_STUDIO_DIR="$RUN_ROOT/data/local-studio"
export AISTUDIO_REQUEST_LOGS_DIR="$RUN_ROOT/data/request-logs"
export AISTUDIO_GENERATED_IMAGES_DIR="$RUN_ROOT/data/generated-images"
export AISTUDIO_IMAGE_SESSIONS_DIR="$RUN_ROOT/data/image-sessions"
export OPENAI_COMPAT_KEY_FILE="${OPENAI_COMPAT_KEY_FILE:-/mnt/c/Users/bamboo/Documents/github/key.txt}"
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

python - <<'PY'
import os
import time
import urllib.request

base = f"http://127.0.0.1:{os.environ['AISTUDIO_PORT']}"
deadline = time.time() + 180
last_error = None
while time.time() < deadline:
    try:
        with urllib.request.urlopen(base + "/api/local-studio/health", timeout=3) as response:
            if response.status == 200:
                raise SystemExit(0)
    except Exception as exc:  # noqa: BLE001 - printed without secrets
        last_error = exc
    time.sleep(2)
raise SystemExit(f"server did not become healthy: {last_error}")
PY

set +e
python "$TASK_REL/verification/run_real_system_smoke.py" --base-url "http://127.0.0.1:$PORT" --artifacts-dir "$SYSTEM_TEST_ARTIFACTS_DIR"
SMOKE_EXIT=$?
set -e

echo "RUN_ROOT=$RUN_ROOT"
echo "SUMMARY=$SYSTEM_TEST_ARTIFACTS_DIR/summary.md"
echo "RESULTS=$SYSTEM_TEST_ARTIFACTS_DIR/results.json"
exit "$SMOKE_EXIT"