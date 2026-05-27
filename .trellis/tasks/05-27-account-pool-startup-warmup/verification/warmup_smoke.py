from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any

import httpx
from playwright.async_api import async_playwright


def safe_text(value: Any, limit: int = 500) -> str:
    return str(value).replace("\n", " ")[:limit]


def wait_for_health(base_url: str) -> None:
    deadline = time.time() + 180
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base_url + "/api/local-studio/health", timeout=3) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001 - sanitized below
            last_error = exc
        time.sleep(2)
    raise RuntimeError(f"server did not become healthy: {safe_text(last_error)}")


def wait_for_warmup_log(server_log: Path) -> dict[str, Any]:
    deadline = time.time() + 90
    text = ""
    while time.time() < deadline:
        if server_log.exists():
            text = server_log.read_text(encoding="utf-8", errors="replace")
            if "Starting account browser warmup" in text:
                break
        time.sleep(2)
    if "Starting account browser warmup" not in text:
        raise RuntimeError("account browser warmup did not start")

    follow_deadline = time.time() + 180
    while time.time() < follow_deadline:
        text = server_log.read_text(encoding="utf-8", errors="replace")
        if "Account browser warmup completed" in text or "Account browser warmup failed" in text:
            break
        time.sleep(2)
    return {
        "started": "Starting account browser warmup" in text,
        "completed": "Account browser warmup completed" in text,
        "failed": "Account browser warmup failed" in text,
    }


async def run_api_smoke(base_url: str) -> dict[str, Any]:
    payload = {
        "model": "gemini-3.1-flash-lite",
        "messages": [{"role": "user", "content": "Reply with exactly pong."}],
        "temperature": 0,
    }
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=420.0) as client:
        response = await client.post(base_url + "/v1/chat/completions", json=payload)
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    data: dict[str, Any] = {}
    try:
        data = response.json()
    except ValueError:
        data = {"raw": response.text[:500]}
    if response.status_code != 200:
        raise RuntimeError(f"API smoke failed HTTP {response.status_code}: {safe_text(data)}")
    content = str(data.get("choices", [{}])[0].get("message", {}).get("content") or "")
    if not content.strip():
        raise RuntimeError("API smoke returned empty assistant content")
    return {"status_code": response.status_code, "elapsed_ms": elapsed_ms, "content_preview": content[:120]}


async def run_ui_smoke(base_url: str, model: str) -> dict[str, Any]:
    console_errors: list[str] = []
    started = time.perf_counter()
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        await page.goto(f"{base_url}/static/index.html#studio", wait_until="domcontentloaded", timeout=60000)
        await page.get_by_role("button", name=re.compile("加载中|加载模型")).click(timeout=20000)
        await page.wait_for_function("Alpine.$data(document.body).localStudioModelsLoading === false", timeout=420000)
        await page.evaluate("model => { Alpine.$data(document.body).localStudioModel = model; }", model)
        await page.locator(".local-studio-compose-row textarea").fill("UI smoke reply ok")
        await page.locator(".local-studio-compose-row button.send").click()
        await page.wait_for_function("Alpine.$data(document.body).localStudioBusy === false", timeout=420000)
        state = await page.evaluate(
            "() => { const app = Alpine.$data(document.body); const msgs = app.localStudioActiveMessages || []; return msgs[msgs.length - 1] || {}; }"
        )
        await browser.close()
    if console_errors:
        raise RuntimeError(f"UI console errors: {safe_text(console_errors[-3:])}")
    content = str(state.get("content") or "") if isinstance(state, dict) else ""
    error = str(state.get("error") or "") if isinstance(state, dict) else ""
    if not content.strip():
        raise RuntimeError(safe_text(error or "UI smoke returned empty assistant content"))
    return {"elapsed_ms": round((time.perf_counter() - started) * 1000), "content_preview": content[:120]}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--server-log", required=True)
    parser.add_argument("--artifacts-dir", required=True)
    args = parser.parse_args()

    artifacts = Path(args.artifacts_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    server_log = Path(args.server_log)

    wait_for_health(args.base_url)
    warmup = wait_for_warmup_log(server_log)
    api = await run_api_smoke(args.base_url)
    ui = await run_ui_smoke(args.base_url, "gemini-3.1-flash-lite")

    results = {"base_url": args.base_url, "warmup": warmup, "api": api, "ui": ui}
    (artifacts / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = [
        "# Account Pool Warmup Real Smoke",
        "",
        f"Base URL: `{args.base_url}`",
        "",
        f"- Warmup started: `{warmup['started']}`",
        f"- Warmup completed: `{warmup['completed']}`",
        f"- Warmup failed log present: `{warmup['failed']}`",
        f"- API chat elapsed: `{api['elapsed_ms']}ms`",
        f"- UI send elapsed: `{ui['elapsed_ms']}ms`",
        "",
    ]
    (artifacts / "summary.md").write_text("\n".join(summary), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())