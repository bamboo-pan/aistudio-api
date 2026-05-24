from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx


def read_openai_config(path: Path) -> tuple[str, str, dict[str, Any]]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").replace("\r", "").split("\n") if line.strip()]
    if len(lines) >= 2 and lines[0].startswith(("http://", "https://")):
        base_url, token = lines[0].rstrip("/"), lines[1]
    elif len(lines) == 1:
        base_url, token = "https://api.openai.com/v1", lines[0]
    else:
        raise RuntimeError("OpenAI-compatible key file must contain token or base URL plus token")
    return base_url, token, {"line_count": len(lines), "base_url_length": len(base_url), "token_length": len(token)}


def choose_model(models: list[dict[str, Any]]) -> str:
    ids = [str(item.get("id") or item.get("name") or "").replace("models/", "") for item in models]
    ids = [model_id for model_id in ids if model_id]
    for wanted in ("gpt-5", "gpt-4.1", "gpt-4o", "gpt"):
        for model_id in ids:
            if model_id == wanted or wanted in model_id:
                return model_id
    if not ids:
        raise RuntimeError("No model candidates returned")
    return ids[0]


async def request_json(client: httpx.AsyncClient, method: str, path: str, *, json_body: Any | None = None) -> dict[str, Any]:
    response = await client.request(method, path, json=json_body)
    try:
        data = response.json()
    except ValueError:
        data = {"raw": response.text[:500]}
    return {"status": response.status_code, "data": data, "ok": response.status_code < 400}


async def stream_local_studio(client: httpx.AsyncClient, payload: dict[str, Any]) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    async with client.stream("POST", "/api/local-studio/chat", json=payload) as response:
        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue
            text = line[6:].strip()
            if not text or text == "[DONE]":
                continue
            events.append(json.loads(text))
    completed = [event for event in events if event.get("type") == "local_studio.completed"]
    if not completed:
        raise AssertionError("Missing local_studio.completed event")
    conversation = completed[-1].get("conversation") if isinstance(completed[-1].get("conversation"), dict) else {}
    messages = conversation.get("messages") if isinstance(conversation.get("messages"), list) else []
    assistant = messages[-1] if messages and isinstance(messages[-1], dict) else {}
    thinking = str(assistant.get("thinking") or "")
    if response.status_code != 200:
        raise AssertionError(f"Expected stream status 200, got {response.status_code}")
    if not thinking.strip():
        raise AssertionError("Streaming Local Studio assistant message did not preserve thinking")
    return {"conversation_id": conversation.get("id"), "assistant_content": str(assistant.get("content") or "")[:120], "thinking_length": len(thinking), "event_count": len(events)}


async def run_ui(base_url: str) -> dict[str, Any]:
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 1100})
        await page.goto(f"{base_url}/static/index.html#studio", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_function("() => document.body.innerText.includes('Reasoning summary')", timeout=60000)
        body = await page.locator("body").inner_text(timeout=30000)
        await browser.close()
    return {"reasoning_summary_visible": "Reasoning summary" in body, "body_has_thinking_label": "Reasoning summary" in body or "思考中" in body}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18082")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--openai-key-file", default="/mnt/c/Users/bamboo/Documents/github/key.txt")
    args = parser.parse_args()

    artifacts = Path(args.run_root) / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    openai_base_url, openai_token, key_meta = read_openai_config(Path(args.openai_key_file))
    timeout = httpx.Timeout(360.0, connect=30.0)
    async with httpx.AsyncClient(base_url=args.base_url, timeout=timeout) as client:
        provider = {"provider_type": "openai", "base_url": openai_base_url, "api_key": openai_token, "interface_mode": "responses", "timeout": 180}
        models = await request_json(client, "POST", "/api/local-studio/models", json_body=provider)
        if not models["ok"]:
            raise AssertionError(f"Model load failed: {models['status']}")
        model = choose_model(models["data"].get("data", []))
        payload = {
            **provider,
            "model": model,
            "message": "Decide whether 17*23 is greater than 390. Give a brief conclusion.",
            "options": {"stream": True, "reasoning_effort": "high", "reasoning_summary": "auto", "cache_enabled": True, "cache_namespace": f"stream-reasoning-{int(time.time())}"},
        }
        api = await stream_local_studio(client, payload)
    ui = await run_ui(args.base_url)
    summary = {"base_url": args.base_url, "run_root": args.run_root, "openai_key_file_meta": key_meta, "api": api, "ui": ui, "failures": []}
    if not ui["reasoning_summary_visible"]:
        summary["failures"].append("UI did not show the Reasoning summary block")
    output = artifacts / "streaming-reasoning-summary.json"
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"base_url": args.base_url, "run_root": args.run_root, "api_thinking_length": api["thinking_length"], "ui": ui, "failures": summary["failures"]}, ensure_ascii=False, indent=2))
    if summary["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())