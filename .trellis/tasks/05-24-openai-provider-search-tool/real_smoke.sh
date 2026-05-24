#!/usr/bin/env bash
set -euo pipefail
set +x

SOURCE_REPO="${SOURCE_REPO:-/mnt/c/Users/bamboo/Desktop/aistudio-api_u1}"
RUN_ROOT="${RUN_ROOT:-/home/bamboo/aistudio-api-openai-search-$(date +%Y%m%d-%H%M%S)}"
KEY_FILE="${OPENAI_COMPAT_KEY_FILE:-/mnt/c/Users/bamboo/Documents/github/key.txt}"

mkdir -p "$RUN_ROOT"
rsync -a --delete \
  --exclude .git \
  --exclude .venv \
  --exclude venv \
  --exclude data/local-studio \
  --exclude data/request-logs \
  --exclude data/generated-images \
  --exclude data/image-sessions \
  "$SOURCE_REPO/" "$RUN_ROOT/repo/"

cd "$RUN_ROOT/repo"
python3 -m venv venv
. venv/bin/activate
python -m pip install -q --upgrade pip setuptools wheel
python -m pip install -q -e . playwright pytest
python -m playwright install firefox >/dev/null

PORT="${AISTUDIO_PORT:-}"
if [ -z "$PORT" ]; then
  PORT=$(python - <<'PY'
import socket
for port in range(18080, 18120):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex(("127.0.0.1", port)) != 0:
            print(port)
            raise SystemExit(0)
raise SystemExit("no free port found")
PY
)
fi

ARTIFACTS="$RUN_ROOT/artifacts"
mkdir -p "$ARTIFACTS/screenshots"

export AISTUDIO_PORT="$PORT"
export AISTUDIO_ACCOUNTS_DIR="${AISTUDIO_ACCOUNTS_DIR:-/home/bamboo/aistudio-api/data/accounts}"
export AISTUDIO_LOCAL_STUDIO_DIR="$RUN_ROOT/data/local-studio"
export AISTUDIO_REQUEST_LOGS_DIR="$RUN_ROOT/data/request-logs"
export AISTUDIO_GENERATED_IMAGES_DIR="$RUN_ROOT/data/generated-images"
export AISTUDIO_IMAGE_SESSIONS_DIR="$RUN_ROOT/data/image-sessions"
export OPENAI_COMPAT_KEY_FILE="$KEY_FILE"
export REAL_SMOKE_ARTIFACTS="$ARTIFACTS"

python main.py server >"$ARTIFACTS/server.log" 2>&1 &
SERVER_PID=$!
cleanup() {
  if kill -0 "$SERVER_PID" >/dev/null 2>&1; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

python - <<'PY'
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

port = int(os.environ["AISTUDIO_PORT"])
base = f"http://127.0.0.1:{port}"
artifacts = Path(os.environ["REAL_SMOKE_ARTIFACTS"])
key_file = Path(os.environ["OPENAI_COMPAT_KEY_FILE"])


def request(method: str, path: str, body: dict | None = None, timeout: int = 180):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            text = raw.decode("utf-8", errors="replace")
            stripped = text.lstrip()
            parsed = json.loads(stripped) if stripped.startswith(("{", "[")) else None
            return resp.status, parsed, text
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        text = raw.decode("utf-8", errors="replace")
        try:
            parsed = json.loads(text) if text else None
        except json.JSONDecodeError:
            parsed = None
        return exc.code, parsed, text


def wait_health():
    last = ""
    for _ in range(120):
        try:
            status, payload, text = request("GET", "/api/local-studio/health", timeout=2)
            if status == 200:
                return payload
            last = text
        except Exception as exc:  # noqa: BLE001 - smoke script summary needs last error
            last = str(exc)
        time.sleep(1)
    raise RuntimeError(f"server did not become healthy: {last}")


def read_provider_credentials():
    if not key_file.exists():
        raise RuntimeError(f"missing OpenAI-compatible key file: {key_file}")
    lines = [line.strip() for line in key_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("OpenAI-compatible key file is empty")
    if lines[0].startswith(("http://", "https://")):
        if len(lines) < 2:
            raise RuntimeError("key file contains a base URL but no token line")
        return lines[0].rstrip("/"), lines[1]
    return os.environ.get("OPENAI_COMPAT_BASE_URL", "https://api.openai.com/v1").rstrip("/"), lines[0]


def assert_no_legacy_error(label: str, text: str):
    if "Unsupported tool type: web_search_preview" in text or "web_search_preview" in text and label.startswith("openai-error"):
        raise AssertionError(f"{label} still contains the legacy unsupported tool error")
    if "ResponseNotRead" in text or "ExceptionGroup" in text or "Exception in ASGI application" in text:
        raise AssertionError(f"{label} contains an unhandled server failure marker")


def parse_log_body(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def request_log_groups():
    status, payload, _ = request("GET", "/request-logs?limit=100")
    if status != 200:
        raise AssertionError(f"request log list failed: {status}")
    return payload.get("data") if isinstance(payload, dict) else []


def find_recent_upstream_tools():
    groups = request_log_groups()
    found = []
    for group in groups[:20]:
        chain_id = group.get("chain_id") or group.get("id")
        if not chain_id:
            continue
        status, detail, _ = request("GET", f"/request-logs/groups/{chain_id}")
        if status != 200 or not isinstance(detail, dict):
            continue
        for entry in detail.get("entries", []):
            if entry.get("phase") != "upstream_request":
                continue
            body = parse_log_body(entry.get("body") or entry.get("body_json"))
            if isinstance(body, dict) and body.get("tools"):
                found.append({"chain_id": chain_id, "tools": body.get("tools"), "url": entry.get("url")})
    return found


api_results: dict[str, object] = {"port": port, "run_root": str(artifacts.parent)}
ui_results: dict[str, object] = {}

wait_health()
for path in ["/api/local-studio/health", "/request-logs/status", "/v1/models", "/v1beta/models"]:
    status, payload, text = request("GET", path, timeout=60)
    api_results[path] = {"status": status, "ok": status == 200}
    if status != 200:
        raise AssertionError(f"bootstrap endpoint failed: {path} -> {status}: {text[:200]}")

status, payload, text = request("PUT", "/request-logs/status", {"enabled": True})
api_results["request_logs_enabled"] = {"status": status, "enabled": payload.get("enabled") if isinstance(payload, dict) else None}
if status != 200 or not isinstance(payload, dict) or payload.get("enabled") is not True:
    raise AssertionError(f"failed to enable request logs: {status}: {text[:200]}")

provider_base_url, provider_token = read_provider_credentials()
model_status, model_payload, model_text = request(
    "POST",
    "/api/local-studio/models",
    {"provider_type": "openai", "base_url": provider_base_url, "api_key": provider_token, "interface_mode": "responses", "timeout": 120},
    timeout=180,
)
api_results["openai_models"] = {"status": model_status, "ok": model_status == 200}
if model_status != 200 or not isinstance(model_payload, dict):
    raise AssertionError(f"OpenAI-compatible models failed: {model_status}: {model_text[:300]}")
models = [item.get("id") for item in model_payload.get("data", []) if isinstance(item, dict) and item.get("id")]
chat_model = next((item for item in models if not item.startswith("gpt-image-")), models[0] if models else "")
if not chat_model:
    raise AssertionError("OpenAI-compatible provider returned no chat model")
api_results["openai_models"]["model_count"] = len(models)
api_results["openai_models"]["selected_model"] = chat_model

chat_body = {
    "provider_type": "openai",
    "base_url": provider_base_url,
    "api_key": provider_token,
    "interface_mode": "responses",
    "model": chat_model,
    "message": "Search one current technology news item and reply in one short sentence.",
    "options": {"stream": False, "search": True, "cache_enabled": False},
    "timeout": 180,
}
chat_status, chat_payload, chat_text = request("POST", "/api/local-studio/chat", chat_body, timeout=240)
assert_no_legacy_error("openai-api-chat", chat_text)
api_results["openai_responses_search_nonstream"] = {"status": chat_status, "controlled": chat_status < 500}
if chat_status >= 500:
    raise AssertionError(f"OpenAI-compatible non-stream search failed as server error: {chat_status}: {chat_text[:300]}")

stream_body = dict(chat_body)
stream_body["message"] = "Search one current technology news item and answer ok plus one word."
stream_body["options"] = {"stream": True, "search": True, "cache_enabled": False}
stream_status, stream_payload, stream_text = request("POST", "/api/local-studio/chat", stream_body, timeout=240)
assert_no_legacy_error("openai-api-stream", stream_text)
api_results["openai_responses_search_stream"] = {"status": stream_status, "controlled": stream_status == 200}
if stream_status != 200:
    raise AssertionError(f"OpenAI-compatible stream search did not return SSE status 200: {stream_status}: {stream_text[:300]}")

tools = find_recent_upstream_tools()
openai_tools = [item for item in tools if item.get("url", "").rstrip("/").endswith("/responses") and any(tool.get("type") == "web_search" for tool in item.get("tools", []) if isinstance(tool, dict))]
legacy_tools = [item for item in tools if any(tool.get("type") == "web_search_preview" for tool in item.get("tools", []) if isinstance(tool, dict)) and "127.0.0.1" not in str(item.get("url", "")) and "testserver" not in str(item.get("url", ""))]
api_results["request_log_tools"] = {"openai_web_search_groups": [item["chain_id"] for item in openai_tools], "legacy_preview_groups": [item["chain_id"] for item in legacy_tools]}
if not openai_tools:
    raise AssertionError("request logs did not show OpenAI-compatible upstream tools using web_search")
if legacy_tools:
    raise AssertionError("request logs showed web_search_preview sent to an OpenAI-compatible upstream")

with sync_playwright() as p:
    browser = p.firefox.launch(headless=True)
    page = browser.new_page(viewport={"width": 1366, "height": 900})
    console_errors: list[str] = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: console_errors.append(str(exc)))
    page.goto(base + "/static/index.html#studio", wait_until="networkidle")
    page.wait_for_function("() => window.Alpine && document.body && window.Alpine.$data(document.body)")
    ui_data = page.evaluate(
        """async ({baseUrl, token, model}) => {
            const app = window.Alpine.$data(document.body);
            app.go('studio');
            const provider = app.addLocalStudioProvider({type:'openai', name:'Smoke OpenAI Provider', baseUrl, apiKey:token, timeout:180, interfaceMode:'responses'});
            app.localStudioProviderId = provider.id;
            app.localStudioProviderType = 'openai';
            app.localStudioSettings = {name:'Smoke OpenAI Provider', baseUrl, apiKey:token, timeout:180};
            app.localStudioInterfaceMode = 'responses';
            app.localStudioSearch = 'on';
            app.localStudioStream = 'on';
            app.localStudioImageToolEnabled = false;
            app.localStudioCacheNamespace = 'real-smoke-openai-search';
            app.saveLocalStudioSettings();
            await app.loadLocalStudioModels();
            app.localStudioModel = model || app.localStudioModelOptions?.[0]?.id || app.localStudioModels?.[0]?.id || '';
            app.localStudioDraft = 'Search one current technology news item and reply in one short sentence.';
            await app.sendLocalStudioMessage();
            return {
              view: app.view,
              model: app.localStudioModel,
              error: app.localStudioError,
              messageCount: app.localStudioActiveMessages.length,
              lastMessage: app.localStudioActiveMessages[app.localStudioActiveMessages.length - 1] || null
            };
        }""",
        {"baseUrl": provider_base_url, "token": provider_token, "model": chat_model},
    )
    page.screenshot(path=str(artifacts / "screenshots" / "local-studio-openai-search.png"), full_page=True)
    browser.close()

ui_text = json.dumps(ui_data, ensure_ascii=False)
assert_no_legacy_error("openai-ui", ui_text)
if console_errors:
    raise AssertionError("browser console/page errors: " + " | ".join(console_errors[:5]))
ui_results["local_studio_openai_search"] = {
    "ok": True,
    "model": chat_model,
    "message_count": ui_data.get("messageCount"),
    "has_error": bool(ui_data.get("error") or (ui_data.get("lastMessage") or {}).get("error")),
    "screenshot": "screenshots/local-studio-openai-search.png",
}

server_log = (artifacts / "server.log").read_text(encoding="utf-8", errors="replace") if (artifacts / "server.log").exists() else ""
assert_no_legacy_error("server-log", server_log)

(artifacts / "api-results.json").write_text(json.dumps(api_results, indent=2, ensure_ascii=False), encoding="utf-8")
(artifacts / "ui-results.json").write_text(json.dumps(ui_results, indent=2, ensure_ascii=False), encoding="utf-8")
(artifacts / "summary.md").write_text(
    "# OpenAI Provider Search Real Smoke\n\n"
    f"- Port: {port}\n"
    f"- Run root: {artifacts.parent}\n"
    f"- Selected model: {chat_model}\n"
    "- API: passed provider-aware search checks without legacy web_search_preview error\n"
    "- UI: opened #studio and sent a streamed Local Studio message without console errors\n",
    encoding="utf-8",
)
print(json.dumps({"run_root": str(artifacts.parent), "port": port, "model": chat_model, "api": "passed", "ui": "passed"}, ensure_ascii=False))
PY