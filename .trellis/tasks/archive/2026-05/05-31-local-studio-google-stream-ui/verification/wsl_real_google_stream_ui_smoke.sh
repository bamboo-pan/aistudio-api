#!/usr/bin/env bash
set -euo pipefail

SOURCE_ROOT="${AISTUDIO_SMOKE_SOURCE:-/mnt/c/Users/bamboo/Desktop/aistudio-api_u1}"
RUN_ROOT="${AISTUDIO_SMOKE_RUN_ROOT:-/home/bamboo/aistudio-api-google-stream-ui-$(date +%Y%m%d-%H%M%S)}"
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

cat >"$RUN_ROOT/real_google_stream_ui_smoke.py" <<'PY'
import asyncio
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx
from playwright.async_api import async_playwright

BASE_URL = os.environ["SMOKE_BASE_URL"].rstrip("/")
ARTIFACT_ROOT = Path(os.environ["SMOKE_ARTIFACT_ROOT"])
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)


def note(message: str) -> None:
    print(f"[smoke] {message}", flush=True)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def model_ids(items):
    return [str(item.get("id") or item.get("name") or "").removeprefix("models/") for item in items if isinstance(item, dict)]


def choose_model(models, preferred):
    available = model_ids(models)
    for model in preferred:
        if model in available:
            return model
    require(bool(available), "no models returned")
    return available[0]


async def wait_for_server(client: httpx.AsyncClient) -> None:
    last_error = ""
    deadline = time.monotonic() + 360
    while time.monotonic() < deadline:
        try:
            response = await client.get(f"{BASE_URL}/health")
            if response.status_code == 200:
                health = response.json()
                warmup = health.get("warmup") if isinstance(health, dict) else {}
                status = str((warmup or {}).get("status") or "")
                note(f"health ok, warmup={status or 'unknown'}")
                if status != "running":
                    return
        except Exception as exc:  # noqa: BLE001 - smoke diagnostics only
            last_error = str(exc)
        await asyncio.sleep(2)
    raise AssertionError(f"server did not become ready: {last_error}")


async def load_models(client: httpx.AsyncClient) -> tuple[str, str]:
    payload = {"provider_type": "google-ai-studio", "interface_mode": "responses", "timeout": 600}
    last_error = ""
    deadline = time.monotonic() + 420
    while time.monotonic() < deadline:
        try:
            response = await client.post(f"{BASE_URL}/api/local-studio/models", json=payload, timeout=120)
            if response.status_code == 200:
                data = response.json()
                chat_models = data.get("data") if isinstance(data, dict) else []
                image_models = data.get("image_models") if isinstance(data, dict) else []
                chat_model = choose_model(chat_models, ["gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-pro"])
                image_model = choose_model(image_models, ["gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview"])
                note(f"selected chat_model={chat_model} image_model={image_model}")
                return chat_model, image_model
            last_error = f"HTTP {response.status_code}: {response.text[:500]}"
        except Exception as exc:  # noqa: BLE001 - smoke diagnostics only
            last_error = str(exc)
        await asyncio.sleep(5)
    raise AssertionError(f"model list did not become ready: {last_error}")


def local_image_tool_payload(chat_model: str, image_model: str, message: str) -> dict:
    return {
        "provider_type": "google-ai-studio",
        "interface_mode": "responses",
        "model": chat_model,
        "message": message,
        "timeout": 600,
        "options": {
            "stream": True,
            "search": False,
            "reasoning_effort": "off",
            "reasoning_summary": "auto",
            "image_tool_enabled": True,
            "image_tool_provider": "google-ai-studio",
            "image_model": image_model,
            "size": "1024x1024",
        },
    }


async def stream_local_studio_chat(client: httpx.AsyncClient, payload: dict) -> tuple[list[tuple[int, dict]], str]:
    events: list[tuple[int, dict]] = []
    raw_text_parts: list[str] = []
    buffer = ""
    chunk_index = 0
    async with client.stream("POST", f"{BASE_URL}/api/local-studio/chat", json=payload, timeout=720) as response:
        if response.status_code >= 400:
            body = await response.aread()
            raise AssertionError(f"chat stream failed HTTP {response.status_code}: {body[:1200]!r}")
        async for chunk in response.aiter_text():
            chunk_index += 1
            raw_text_parts.append(chunk)
            buffer += chunk
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if not line.startswith("data: "):
                    continue
                data_text = line[6:].strip()
                if not data_text or data_text == "[DONE]":
                    continue
                try:
                    events.append((chunk_index, json.loads(data_text)))
                except json.JSONDecodeError:
                    continue
    return events, "".join(raw_text_parts)


async def verify_api_image_tool_progress(client: httpx.AsyncClient, chat_model: str, image_model: str) -> None:
    note("API image-tool stream progress check")
    payload = local_image_tool_payload(
        chat_model,
        image_model,
        "Use the image_generation tool to create a simple flat test image: a red square centered on a white background.",
    )
    events, raw_text = await stream_local_studio_chat(client, payload)
    require("Requested entity was not found" not in raw_text, "image generation returned requested-entity-not-found")
    errors = [event for _, event in events if event.get("type") == "error" or event.get("error")]
    require(not errors, f"image stream emitted errors: {errors[:2]}")
    progress = [
        (index, event)
        for index, event in events
        if event.get("type") == "local_studio.delta" and "Tool call requested: image_generation" in str(event.get("thinking") or "")
    ]
    completions = [(index, event) for index, event in events if event.get("type") == "local_studio.completed"]
    require(progress, "image stream did not emit tool progress delta")
    require(completions, "image stream did not emit local_studio.completed")
    require(progress[0][0] < completions[-1][0], "tool progress did not arrive before completion chunk")
    conversation = completions[-1][1].get("conversation") or {}
    messages = conversation.get("messages") if isinstance(conversation, dict) else []
    assistant = messages[-1] if isinstance(messages, list) and messages else {}
    images = assistant.get("images") if isinstance(assistant, dict) else []
    require(isinstance(images, list) and images, "image stream completed without generated images")
    require("Tool call requested: image_generation" in str(assistant.get("thinking") or ""), "completed conversation lost tool progress trace")
    image_url = str(images[0].get("url") or "")
    require(image_url, "generated image missing public URL")
    asset_url = image_url if image_url.startswith("http") else urljoin(BASE_URL + "/", image_url.lstrip("/"))
    asset = await client.get(asset_url, timeout=60)
    require(asset.status_code == 200, f"generated asset URL returned HTTP {asset.status_code}")
    require(asset.headers.get("content-type", "").startswith("image/"), f"generated asset content-type is {asset.headers.get('content-type')}")
    require(len(asset.content) > 100, "generated asset is unexpectedly small")
    note(f"API image-tool progress ok: progress_chunk={progress[0][0]} completed_chunk={completions[-1][0]} asset_bytes={len(asset.content)}")


async def verify_request_logs(client: httpx.AsyncClient) -> None:
    status = await client.get(f"{BASE_URL}/request-logs/status")
    require(status.status_code == 200, f"request log status HTTP {status.status_code}")
    data = status.json()
    require(data.get("enabled") is True, "request logging was not enabled")
    require(int(data.get("count") or 0) > 0, "request logging did not capture smoke traffic")
    logs = await client.get(f"{BASE_URL}/request-logs")
    require(logs.status_code == 200, f"request log list HTTP {logs.status_code}")
    require("Bearer " not in logs.text or "Bearer ***" in logs.text, "request logs may include an unredacted bearer token")
    note(f"request logs ok: entries={data.get('count')}")


async def verify_ui(chat_model: str, image_model: str) -> None:
    note("browser UI stream progress check")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 980})
        page = await context.new_page()
        page.on("console", lambda msg: print(f"[browser:{msg.type}] {msg.text}", flush=True) if msg.type in {"error", "warning"} else None)
        await page.goto(BASE_URL, wait_until="domcontentloaded")
        await page.evaluate(
            """
            ([chatModel, imageModel]) => {
              localStorage.setItem('openai.localStudio.settings.v1', JSON.stringify({
                providers:[{id:'google-ai-studio', name:'Google AI Studio', type:'google-ai-studio', timeout:600, interfaceMode:'responses'}],
                providerId:'google-ai-studio', provider_id:'google-ai-studio', providerType:'google-ai-studio', provider_type:'google-ai-studio',
                name:'Google AI Studio', timeout:600, interfaceMode:'responses', model:chatModel, imageModel:imageModel, image_model:imageModel,
                stream:'on', reasoningEffort:'off', reasoningSummary:'auto', search:'off', imageToolEnabled:true, imageSize:'1024x1024',
                imageQuality:'auto', imageBackground:'auto', imageFormat:'png', imageCompression:100
              }));
            }
            """,
            [chat_model, image_model],
        )
        await page.goto(f"{BASE_URL}/#studio", wait_until="networkidle")
        await page.get_by_role("button", name=re.compile("加载模型|加载中")).click(timeout=15000)
        await page.wait_for_function(
            """
            ([chatModel, imageModel]) => {
              const root = document.querySelector('[x-data]');
              const data = root && root._x_dataStack && root._x_dataStack[0];
              return !!data && data.localStudioModel === chatModel && data.localStudioImageModel === imageModel && !data.localStudioModelsLoading;
            }
            """,
            arg=[chat_model, image_model],
            timeout=150000,
        )
        textarea = page.locator("#studio-page textarea").last
        await textarea.fill("Use the image_generation tool to create a simple flat test image: a yellow triangle on a white background.")
        await page.locator("#studio-page button.send").click()
        await page.wait_for_function(
            """
            () => {
              const root = document.querySelector('[x-data]');
              const data = root && root._x_dataStack && root._x_dataStack[0];
              const messages = data && Array.isArray(data.localStudioActiveMessages) ? data.localStudioActiveMessages : [];
              const assistant = [...messages].reverse().find(message => message && message.role === 'assistant');
              return !!data && data.localStudioBusy && !!assistant && String(assistant.thinking || '').includes('Tool call requested: image_generation');
            }
            """,
            timeout=300000,
        )
        await page.wait_for_function(
            """() => !Array.from(document.querySelectorAll('.local-studio-message.is-pending')).some(el => getComputedStyle(el).display !== 'none')""",
            timeout=480000,
        )
        await page.wait_for_function(
            """
            () => Array.from(document.querySelectorAll('.local-studio-images img')).some(img => img.complete && img.naturalWidth > 0 && img.naturalHeight > 0)
            """,
            timeout=120000,
        )
        visible_errors = await page.locator(".msg-body.error:visible").all_text_contents()
        require(not any("Requested entity was not found" in text for text in visible_errors), "UI still shows requested-entity-not-found")
        await page.screenshot(path=str(ARTIFACT_ROOT / "local-studio-google-stream-ui.png"), full_page=True)
        await browser.close()
        note("browser UI progress ok")


async def main() -> None:
    async with httpx.AsyncClient(timeout=60) as client:
        await wait_for_server(client)
        enable = await client.put(f"{BASE_URL}/request-logs/status", json={"enabled": True})
        require(enable.status_code == 200 and enable.json().get("enabled") is True, "failed to enable request logs")
        chat_model, image_model = await load_models(client)
        await verify_api_image_tool_progress(client, chat_model, image_model)
        await verify_request_logs(client)
    await verify_ui(chat_model, image_model)


if __name__ == "__main__":
    asyncio.run(main())
PY

if ! python "$RUN_ROOT/real_google_stream_ui_smoke.py"; then
  echo "[smoke] FAILED. Last server log lines:" >&2
  tail -n 220 "$SERVER_LOG" >&2 || true
  exit 1
fi

echo "[smoke] PASS"
echo "[smoke] artifacts: $ARTIFACT_ROOT"
