#!/usr/bin/env bash
set -euo pipefail

SOURCE_ROOT="${AISTUDIO_SMOKE_SOURCE:-/mnt/c/Users/bamboo/Desktop/aistudio-api_u1}"
RUN_ROOT="${AISTUDIO_SMOKE_RUN_ROOT:-/home/bamboo/aistudio-api-stream-rendering-$(date +%Y%m%d-%H%M%S)}"
REPO_ROOT="$RUN_ROOT/repo"
ARTIFACT_ROOT="$RUN_ROOT/artifacts"
PORT="${AISTUDIO_SMOKE_PORT:-$((18080 + RANDOM % 1000))}"
CAMOUFOX_PORT="${AISTUDIO_SMOKE_CAMOUFOX_PORT:-$((19300 + RANDOM % 1000))}"
BASE_URL="http://127.0.0.1:$PORT"

mkdir -p "$REPO_ROOT" "$ARTIFACT_ROOT" "$RUN_ROOT/data/local-studio" "$RUN_ROOT/data/request-logs" "$RUN_ROOT/data/generated-images" "$RUN_ROOT/data/image-sessions"

echo "[smoke] run root: $RUN_ROOT"
echo "[smoke] copying workspace"
rsync -a --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude 'venv/' \
  --exclude '__pycache__/' \
  "$SOURCE_ROOT/" "$REPO_ROOT/"

cd "$REPO_ROOT"

echo "[smoke] creating virtual environment"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
python -m pip install -e . >/dev/null
python -m playwright install chromium >/dev/null

export AISTUDIO_ACCOUNTS_DIR="${AISTUDIO_ACCOUNTS_DIR:-/home/bamboo/aistudio-api/data/accounts}"
export AISTUDIO_LOCAL_STUDIO_DIR="$RUN_ROOT/data/local-studio"
export AISTUDIO_REQUEST_LOGS_DIR="$RUN_ROOT/data/request-logs"
export AISTUDIO_GENERATED_IMAGES_DIR="$RUN_ROOT/data/generated-images"
export AISTUDIO_IMAGE_SESSIONS_DIR="$RUN_ROOT/data/image-sessions"
export AISTUDIO_ACCOUNT_WARMUP_LIMIT="${AISTUDIO_ACCOUNT_WARMUP_LIMIT:-1}"
if [[ -z "${AISTUDIO_PROXY_SERVER:-}" ]]; then
  AISTUDIO_PROXY_SERVER="$(python3 - <<'PY'
import os
for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
    value = os.environ.get(key)
    if value:
        print(value, end="")
        break
PY
)"
  if [[ -z "$AISTUDIO_PROXY_SERVER" ]]; then
    AISTUDIO_PROXY_SERVER="$(bash -lc 'env' | awk -F= '$1=="HTTPS_PROXY"{print substr($0,index($0,"=")+1); exit} $1=="https_proxy"{print substr($0,index($0,"=")+1); exit} $1=="HTTP_PROXY"{print substr($0,index($0,"=")+1); exit} $1=="http_proxy"{print substr($0,index($0,"=")+1); exit}')"
  fi
  export AISTUDIO_PROXY_SERVER
fi
export SMOKE_BASE_URL="$BASE_URL"
export SMOKE_ARTIFACT_ROOT="$ARTIFACT_ROOT"

SERVER_LOG="$ARTIFACT_ROOT/server.log"
echo "[smoke] starting API server on $BASE_URL (camoufox $CAMOUFOX_PORT)"
python main.py server --port "$PORT" --camoufox-port "$CAMOUFOX_PORT" >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!

cleanup() {
  if kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

cat >"$RUN_ROOT/real_stream_rendering_smoke.py" <<'PY'
import asyncio
import json
import os
import time
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

BASE_URL = os.environ["SMOKE_BASE_URL"].rstrip("/")
ARTIFACT_ROOT = Path(os.environ["SMOKE_ARTIFACT_ROOT"])
OPENAI_KEY_PATH = Path("/mnt/c/Users/bamboo/Documents/github/key.txt")
RUN_ID = f"stream-rendering-{int(time.time())}"
MARKER = f"STREAM_RENDER_MARKER_{RUN_ID}"


def fail(message, details=None):
    payload = {"ok": False, "message": message, "details": details or {}, "run_id": RUN_ID}
    (ARTIFACT_ROOT / "stream_rendering_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    raise AssertionError(message)


def note(message):
    print(f"[smoke] {message}", flush=True)


def read_openai_credentials():
    lines = [line.strip() for line in OPENAI_KEY_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    base_url = "https://api.openai.com/v1"
    token = ""
    for line in lines:
        if line.startswith(("http://", "https://")):
            base_url = line.rstrip("/")
        elif "=" in line:
            key, value = line.split("=", 1)
            lowered = key.strip().lower()
            if lowered in {"base_url", "api_base", "openai_base_url"}:
                base_url = value.strip().rstrip("/")
            elif lowered in {"api_key", "token", "openai_api_key"}:
                token = value.strip()
        elif not token:
            token = line
    if not token:
        fail("OpenAI-compatible key file did not contain a token")
    return base_url, token


async def wait_for_server(client):
    deadline = time.monotonic() + 240
    last_error = ""
    while time.monotonic() < deadline:
        try:
            response = await client.get(f"{BASE_URL}/health")
            if response.status_code == 200:
                health = response.json()
                warmup = health.get("warmup") if isinstance(health, dict) else {}
                status = str((warmup or {}).get("status") or "unknown")
                note(f"health ok, warmup={status}")
                if status != "running":
                    return
        except Exception as exc:  # noqa: BLE001 - smoke diagnostics only
            last_error = str(exc)
        await asyncio.sleep(2)
    fail("server did not become ready", {"last_error": last_error})


async def request_json(client, method, path, **kwargs):
    response = await client.request(method, BASE_URL + path, **kwargs)
    if response.status_code >= 400:
        fail(f"{method} {path} failed", {"status": response.status_code, "body_prefix": response.text[:700]})
    return response.json(), response


def choose_model(models):
    ids = [str(item.get("id") or item.get("name") or "") for item in models if isinstance(item, dict)]
    preferred = ["gpt-4.1-mini", "gpt-4o-mini", "gpt-4.1-nano", "o4-mini", "gpt-4o"]
    for model in preferred:
        if model in ids:
            return model
    for model in ids:
        lowered = model.lower()
        if model and "image" not in lowered and "audio" not in lowered and "embedding" not in lowered:
            return model
    fail("No usable OpenAI-compatible model returned", {"ids": ids[:20]})


def iter_sse_lines(buffer, chunk):
    buffer += chunk
    lines = []
    while "\n" in buffer:
        line, buffer = buffer.split("\n", 1)
        lines.append(line.strip("\r"))
    return buffer, lines


async def api_stream_check(client, base_url, token, model):
    prompt = f"The first line must be exactly {MARKER}. Then write the numbers 1 through 120, one per line, with no extra prose."
    payload = {
        "provider_type": "openai",
        "base_url": base_url,
        "api_key": token,
        "interface_mode": "responses",
        "model": model,
        "message": prompt,
        "timeout": 240,
        "options": {"stream": True, "search": False, "reasoning_effort": "off"},
    }
    started = time.perf_counter()
    first_delta_seconds = None
    first_delta_chunk = None
    completed_chunk = None
    chunk_index = 0
    delta_content = []
    buffer = ""
    async with client.stream("POST", f"{BASE_URL}/api/local-studio/chat", json=payload, timeout=300) as response:
        if response.status_code >= 400:
            body = await response.aread()
            fail("API stream request failed", {"status": response.status_code, "body_prefix": body[:1000].decode(errors="replace")})
        if response.headers.get("cache-control") != "no-cache" or response.headers.get("x-accel-buffering") != "no":
            fail("API stream missing no-buffer headers", {"headers": dict(response.headers)})
        async for chunk in response.aiter_text():
            chunk_index += 1
            buffer, lines = iter_sse_lines(buffer, chunk)
            for line in lines:
                if not line.startswith("data: "):
                    continue
                try:
                    event = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "local_studio.delta":
                    piece = str(event.get("content") or event.get("thinking") or "")
                    if piece:
                        delta_content.append(piece)
                        if first_delta_seconds is None:
                            first_delta_seconds = time.perf_counter() - started
                            first_delta_chunk = chunk_index
                elif event.get("type") == "local_studio.completed":
                    completed_chunk = chunk_index
                    break
                elif event.get("type") == "error" or event.get("error"):
                    fail("API stream returned error event", {"event": event})
            if completed_chunk is not None:
                break
    if first_delta_seconds is None:
        fail("API stream produced no visible delta before completion")
    if completed_chunk is None or not (first_delta_chunk < completed_chunk):
        fail("API stream first visible delta was not before completion", {"first_delta_chunk": first_delta_chunk, "completed_chunk": completed_chunk})
    if first_delta_seconds > 45:
        fail("API stream first visible delta was too slow", {"first_delta_seconds": round(first_delta_seconds, 3)})
    return {"first_delta_seconds": round(first_delta_seconds, 3), "first_delta_chunk": first_delta_chunk, "completed_chunk": completed_chunk, "delta_prefix": "".join(delta_content)[:120]}


async def ui_stream_dom_check(base_url, token, model):
    prompt = f"The first line must be exactly {MARKER}. Then write the numbers 1 through 160, one per line, with no extra prose."
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        try:
            await page.goto(f"{BASE_URL}/#studio", wait_until="networkidle")
            await page.wait_for_function("() => document.body._x_dataStack && document.body._x_dataStack[0]", timeout=60000)
            versioned = await page.evaluate("() => Array.from(document.scripts).some(script => String(script.src).includes('/static/app.js?v=20260531-stream-rendering'))")
            if not versioned:
                fail("Local Studio page did not load versioned app.js")
            model_info = await page.evaluate(
                """async ({baseUrl, token, model}) => {
                    const app = document.body._x_dataStack[0];
                    const provider = {id:'ui-stream-openai', type:'openai', providerType:'openai', name:'UI Stream OpenAI', baseUrl, apiKey:token, timeout:240, interfaceMode:'responses'};
                    app.localStudioProviders = [provider];
                    app.localStudioProviderId = provider.id;
                    app.localStudioProviderType = 'openai';
                    app.localStudioSettings = {name:provider.name, baseUrl, apiKey:token, timeout:240};
                    app.localStudioInterfaceMode = 'responses';
                    app.localStudioStream = 'on';
                    app.localStudioSearch = 'off';
                    app.localStudioReasoningEffort = 'off';
                    app.localStudioImageToolEnabled = false;
                    app.localStudioModels = [{id:model, capabilities:{streaming:true, thinking:true, text_output:true, file_input:true, image_input:true}}];
                    app.localStudioModel = model;
                    app.localStudioConversation = null;
                    app.localStudioConversations = [];
                    app.saveLocalStudioSettings();
                    return {model: app.localStudioModel, canSend: app.localStudioCanSend};
                }""",
                {"baseUrl": base_url, "token": token, "model": model},
            )
            if model_info.get("model") != model:
                fail("UI did not keep selected Local Studio model", model_info)
            textarea = page.locator("textarea[placeholder^='向 Local Studio']")
            await textarea.fill(prompt)
            await page.locator(".local-studio-compose-row button.send").click()
            await page.wait_for_function("() => document.body._x_dataStack[0].localStudioBusy === true", timeout=30000)
            started = time.perf_counter()
            visible_during_busy = False
            state_had_content_without_dom = False
            first_visible_seconds = None
            max_dom_len = 0
            final_content = ""
            while True:
                state = await page.evaluate(
                    """() => {
                        const app = document.body._x_dataStack[0];
                        const messages = app.localStudioActiveMessages || [];
                        const assistant = [...messages].reverse().find(message => message && message.role === 'assistant') || {};
                        const transcript = document.querySelector('#local-studio-scroll')?.innerText || '';
                        return {busy: app.localStudioBusy, content: assistant.content || '', error: app.localStudioError || assistant.error || '', transcript};
                    }"""
                )
                if state["error"]:
                    fail("UI stream showed an error", {"error": state["error"][:600]})
                content = state["content"]
                transcript = state["transcript"]
                if state["busy"] and content.strip():
                    sample = content.strip()[: min(24, len(content.strip()))]
                    if sample and sample not in transcript:
                        state_had_content_without_dom = True
                    if sample and sample in transcript:
                        visible_during_busy = True
                        max_dom_len = max(max_dom_len, len(transcript))
                        if first_visible_seconds is None:
                            first_visible_seconds = time.perf_counter() - started
                if not state["busy"]:
                    final_content = content
                    break
                if time.perf_counter() - started > 240:
                    fail("UI stream did not finish in time")
                await page.wait_for_timeout(250)
            if not final_content.strip():
                fail("UI final assistant content was empty")
            if not visible_during_busy:
                fail("UI did not show streamed content in DOM while request was busy", {"state_had_content_without_dom": state_had_content_without_dom})
            await page.screenshot(path=str(ARTIFACT_ROOT / "stream_rendering_ui.png"), full_page=True)
            return {"first_visible_seconds": round(first_visible_seconds or 0, 3), "max_dom_len": max_dom_len, "state_had_content_without_dom": state_had_content_without_dom, "final_len": len(final_content)}
        finally:
            await browser.close()


async def request_log_check(client, token):
    data, _ = await request_json(client, "GET", "/request-logs?limit=80")
    list_text = json.dumps(data, ensure_ascii=False)
    if token and token in list_text:
        fail("Request log list leaked API token")
    groups = []
    for item in data.get("data", []):
        group_id = item.get("id") if isinstance(item, dict) else None
        if not group_id:
            continue
        group, _ = await request_json(client, "GET", f"/request-logs/groups/{group_id}")
        groups.append(group)
    group_text = json.dumps(groups, ensure_ascii=False)
    if token and token in group_text:
        fail("Request log detail leaked API token")
    matching = [group for group in groups if MARKER in json.dumps(group, ensure_ascii=False)]
    upstream = [group for group in matching if "upstream_request" in [entry.get("phase") for entry in group.get("entries", [])]]
    return {"matching_groups": len(matching), "upstream_request_groups": len(upstream)}


async def main():
    base_url, token = read_openai_credentials()
    summary = {"ok": True, "run_id": RUN_ID, "marker": MARKER}
    async with httpx.AsyncClient(timeout=80) as client:
        await wait_for_server(client)
        await request_json(client, "PUT", "/request-logs/status", json={"enabled": True})
        models, _ = await request_json(client, "POST", "/api/local-studio/models", json={"provider_type": "openai", "base_url": base_url, "api_key": token, "interface_mode": "responses", "timeout": 180})
        model = choose_model(models.get("data") or [])
        summary["selected_model"] = model
        summary["api_stream"] = await api_stream_check(client, base_url, token, model)
        summary["ui_stream"] = await ui_stream_dom_check(base_url, token, model)
        summary["request_logs"] = await request_log_check(client, token)
    (ARTIFACT_ROOT / "stream_rendering_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
PY

python "$RUN_ROOT/real_stream_rendering_smoke.py"