from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from playwright.async_api import async_playwright


@dataclass
class CaseResult:
    case_id: str
    layer: str
    status: str
    detail: str
    elapsed_ms: int = 0


class Runner:
    def __init__(self, base_url: str, artifacts_dir: Path) -> None:
        self.base_url = base_url.rstrip("/")
        self.artifacts_dir = artifacts_dir
        self.results: list[CaseResult] = []
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(420.0, connect=30.0))

    async def close(self) -> None:
        await self.client.aclose()

    def add(self, case_id: str, layer: str, status: str, detail: str, started: float | None = None) -> None:
        elapsed = int((time.perf_counter() - started) * 1000) if started else 0
        self.results.append(CaseResult(case_id, layer, status, detail, elapsed))
        print(f"[{status}] {case_id}: {detail}")

    async def get_json(self, path: str) -> tuple[int, Any]:
        response = await self.client.get(self.base_url + path)
        return response.status_code, response.json()

    async def post_json(self, path: str, payload: dict[str, Any]) -> tuple[int, Any]:
        response = await self.client.post(self.base_url + path, json=payload)
        try:
            body: Any = response.json()
        except ValueError:
            body = response.text
        return response.status_code, body

    async def stream_chat(self, payload: dict[str, Any]) -> tuple[int, str, list[dict[str, Any]]]:
        events: list[dict[str, Any]] = []
        text_parts: list[str] = []
        async with self.client.stream("POST", self.base_url + "/api/local-studio/chat", json=payload, timeout=420.0) as response:
            status = response.status_code
            async for line in response.aiter_lines():
                text_parts.append(line)
                if not line.startswith("data: "):
                    continue
                data_text = line[6:].strip()
                if not data_text or data_text == "[DONE]":
                    continue
                try:
                    parsed = json.loads(data_text)
                except ValueError:
                    continue
                if isinstance(parsed, dict):
                    events.append(parsed)
        return status, "\n".join(text_parts), events

    async def run_boot(self) -> None:
        started = time.perf_counter()
        try:
            status, body = await self.get_json("/api/local-studio/health")
            assert status == 200 and body.get("ok") is True
            await self.client.put(self.base_url + "/request-logs/status", json={"enabled": True})
            status, logs = await self.get_json("/request-logs/status")
            assert status == 200 and logs.get("enabled") is True
        except Exception as exc:  # noqa: BLE001
            self.add("BOOT-01", "api", "fail", safe_text(exc), started)
            return
        self.add("BOOT-01", "api", "pass", "service healthy and request logs enabled", started)

    async def google_models(self, mode: str = "responses") -> list[dict[str, Any]]:
        payload = {"provider_type": "google-ai-studio", "interface_mode": mode, "timeout": 180}
        status, body = await self.post_json("/api/local-studio/models", payload)
        if status != 200 or not isinstance(body, dict):
            raise AssertionError(f"google models failed: {status} {safe_text(body)}")
        models = body.get("data") if isinstance(body.get("data"), list) else []
        if not models:
            raise AssertionError("google models list is empty")
        return models

    async def run_google_api(self) -> str | None:
        started = time.perf_counter()
        try:
            models = await self.google_models("responses")
            model = pick_model(models, ["gemini-3.5-flash", "gemini-3-flash", "gemini"])
        except Exception as exc:  # noqa: BLE001
            self.add("API-LS-01", "api", "fail", safe_text(exc), started)
            return None
        self.add("API-LS-01", "api", "pass", f"google responses models loaded; selected {model}", started)

        google_basic_ok = False
        started = time.perf_counter()
        try:
            status, body = await self.post_json(
                "/api/local-studio/chat",
                {
                    "provider_type": "google-ai-studio",
                    "interface_mode": "responses",
                    "model": model,
                    "message": "回复 ok",
                    "options": {"stream": False, "search": False, "cache_enabled": True, "cache_namespace": "real-api-google-basic"},
                },
            )
            if status != 200:
                raise AssertionError(f"HTTP {status}: {safe_text(body)}")
            if not isinstance(body, dict):
                raise AssertionError(f"non-JSON response: {safe_text(body)}")
            messages = body.get("conversation", {}).get("messages")
            if not isinstance(messages, list) or not messages:
                raise AssertionError(f"missing conversation messages: {safe_text(body)}")
            assistant = next((message for message in reversed(messages) if message.get("role") == "assistant"), None)
            if not assistant:
                raise AssertionError(f"missing assistant message: {safe_text(messages)}")
            if assistant.get("error"):
                raise AssertionError(f"assistant error: {safe_text(assistant.get('error'))}")
            if not str(assistant.get("content") or "").strip():
                raise AssertionError(f"assistant content empty: {safe_text(assistant)}")
        except Exception as exc:  # noqa: BLE001
            self.add("API-LS-03", "api", "fail", safe_text(exc), started)
        else:
            google_basic_ok = True
            self.add("API-LS-03", "api", "pass", "google non-stream chat completed", started)

        if not google_basic_ok:
            self.add(
                "BUG-GEMINI-IMAGE-TOOL-01",
                "api",
                "skip",
                "blocked because Google AI Studio browser capture did not complete the basic chat path",
            )
            return None

        started = time.perf_counter()
        try:
            conversation_id = None
            for prompt, opts in [
                ("你好，只回复一句问候", {"stream": True, "search": False, "cache_enabled": False}),
                ("你是谁，只回复一句话", {"stream": True, "search": False, "cache_enabled": False}),
                ("搜索今天一条科技新闻并用一句话总结", {"stream": True, "search": True, "cache_enabled": False}),
                (
                    "做成图片",
                    {
                        "stream": True,
                        "search": True,
                        "cache_enabled": False,
                        "image_tool_enabled": True,
                        "image_tool_provider": "google-ai-studio",
                        "image_model": "gemini-3.1-flash-image-preview",
                        "size": "1024x1024",
                    },
                ),
            ]:
                payload: dict[str, Any] = {
                    "provider_type": "google-ai-studio",
                    "interface_mode": "responses",
                    "model": model,
                    "message": prompt,
                    "options": opts,
                    "timeout": 300,
                }
                if conversation_id:
                    payload["conversation_id"] = conversation_id
                status, raw, events = await self.stream_chat(payload)
                assert status == 200, raw[-500:]
                assert "include_server_side_tool_invocations" not in raw, raw[-800:]
                assert "Exception in ASGI application" not in server_log_text(), "server ASGI exception during Gemini image path"
                completed = latest_completed(events)
                if completed and completed.get("conversation", {}).get("id"):
                    conversation_id = completed["conversation"]["id"]
                errors = [event for event in events if event.get("type") == "error" or event.get("error")]
                assert not errors, safe_text(errors[-1] if errors else "")
            assert conversation_id
        except Exception as exc:  # noqa: BLE001
            self.add("BUG-GEMINI-IMAGE-TOOL-01", "api", "fail", safe_text(exc), started)
        else:
            self.add("BUG-GEMINI-IMAGE-TOOL-01", "api", "pass", "Gemini search+image stream path completed without reported error", started)

        return model

    async def run_openai_api(self) -> tuple[str | None, str | None]:
        started = time.perf_counter()
        try:
            provider = load_openai_provider()
            status, body = await self.post_json(
                "/api/local-studio/models",
                {
                    "provider_type": "openai",
                    "base_url": provider["base_url"],
                    "api_key": provider["api_key"],
                    "interface_mode": "responses",
                    "timeout": 180,
                },
            )
            assert status == 200, safe_text(body)
            models = body.get("data") if isinstance(body, dict) and isinstance(body.get("data"), list) else []
            assert models, "OpenAI-compatible models list is empty"
            model = pick_model(models, ["gpt-", "gemini", "claude"])
        except Exception as exc:  # noqa: BLE001
            self.add("API-LS-02", "api", "fail", safe_text(exc), started)
            return None, None
        self.add("API-LS-02", "api", "pass", f"OpenAI-compatible models loaded; selected {model}", started)

        started = time.perf_counter()
        try:
            status, raw, events = await self.stream_chat(
                {
                    "provider_type": "openai",
                    "base_url": provider["base_url"],
                    "api_key": provider["api_key"],
                    "interface_mode": "responses",
                    "model": model,
                    "message": "搜索今天一条科技新闻并总结",
                    "options": {"stream": True, "search": True, "cache_enabled": False},
                    "timeout": 240,
                }
            )
            assert status == 200, raw[-500:]
            log_text = server_log_text()
            assert "ResponseNotRead" not in log_text, "server log contains ResponseNotRead"
            assert "Exception in ASGI application" not in log_text, "server log contains ASGI exception"
            assert any(event.get("type") in {"local_studio.completed", "error"} or event.get("error") for event in events), raw[-500:]
            status, health = await self.get_json("/api/local-studio/health")
            assert status == 200 and health.get("ok") is True
        except Exception as exc:  # noqa: BLE001
            self.add("BUG-OPENAI-SEARCH-STREAM-01", "api", "fail", safe_text(exc), started)
        else:
            self.add("BUG-OPENAI-SEARCH-STREAM-01", "api", "pass", "stream search path returned controlled SSE and server stayed healthy", started)
        return provider["base_url"], model

    async def run_ui(self, google_model: str | None, openai_base_url: str | None, openai_model: str | None) -> None:
        started = time.perf_counter()
        console_errors: list[str] = []
        try:
            async with async_playwright() as playwright:
                browser = await playwright.firefox.launch(headless=True)
                page = await browser.new_page(viewport={"width": 1440, "height": 1000})
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                for route in ["studio", "chat", "images", "requests", "accounts"]:
                    await page.goto(f"{self.base_url}/static/index.html#{route}", wait_until="domcontentloaded")
                    await page.wait_for_timeout(800)
                    title = await page.locator(".topbar-title").inner_text(timeout=10000)
                    assert title.strip(), f"empty title at #{route}"
                assert not console_errors, console_errors[-3:]
                await browser.close()
        except Exception as exc:  # noqa: BLE001
            self.add("BOOT-02", "ui", "fail", safe_text(exc), started)
        else:
            self.add("BOOT-02", "ui", "pass", "all primary routes loaded without console errors", started)

        if not google_model:
            self.add(
                "G-LS-01",
                "ui",
                "skip",
                "blocked because Google AI Studio browser capture did not complete the basic API path",
            )
        else:
            started = time.perf_counter()
            console_errors = []
            try:
                async with async_playwright() as playwright:
                    browser = await playwright.firefox.launch(headless=True)
                    page = await browser.new_page(viewport={"width": 1440, "height": 1000})
                    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                    await page.goto(f"{self.base_url}/static/index.html#studio", wait_until="domcontentloaded")
                    await page.get_by_role("button", name=re.compile("加载中|加载模型")).click(timeout=20000)
                    await page.wait_for_function("Alpine.$data(document.body).localStudioModelsLoading === false", timeout=420000)
                    await page.evaluate("model => { Alpine.$data(document.body).localStudioModel = model; }", google_model)
                    await page.locator(".local-studio-compose-row textarea").fill("UI smoke 回复 ok")
                    await page.locator(".local-studio-compose-row button.send").click()
                    await page.wait_for_function("Alpine.$data(document.body).localStudioBusy === false", timeout=420000)
                    state = await page.evaluate(
                        "() => { const app = Alpine.$data(document.body); const msgs = app.localStudioActiveMessages || []; return msgs[msgs.length - 1] || {}; }"
                    )
                    assert state and state.get("content"), safe_text(state.get("error") or "no assistant content rendered")
                    assert not console_errors, console_errors[-3:]
                    await browser.close()
            except Exception as exc:  # noqa: BLE001
                self.add("G-LS-01", "ui", "fail", safe_text(exc), started)
            else:
                self.add("G-LS-01", "ui", "pass", "Google Local Studio UI loaded models and sent a message", started)

        started = time.perf_counter()
        if not (openai_base_url and openai_model):
            self.add("O-LS-01", "ui", "skip", "OpenAI-compatible API model setup failed or was unavailable")
            return
        started = time.perf_counter()
        console_errors = []
        try:
            provider = load_openai_provider(openai_base_url)
            async with async_playwright() as playwright:
                browser = await playwright.firefox.launch(headless=True)
                page = await browser.new_page(viewport={"width": 1440, "height": 1000})
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                await page.goto(f"{self.base_url}/static/index.html#studio", wait_until="domcontentloaded")
                await page.get_by_role("button", name="新增").click(timeout=20000)
                await page.locator("label.local-studio-field", has_text="Provider Name").locator("input").fill("System Test Provider")
                await page.locator("label.local-studio-field", has_text="Base URL").locator("input").fill(provider["base_url"])
                await page.locator("label.local-studio-field", has_text="API Token").locator("input").fill(provider["api_key"])
                await page.get_by_role("button", name=re.compile("加载中|加载模型")).click(timeout=20000)
                await page.wait_for_function("Alpine.$data(document.body).localStudioModelsLoading === false", timeout=420000)
                await page.evaluate("model => { Alpine.$data(document.body).localStudioModel = model; }", openai_model)
                await page.locator(".runtime-toggle", has_text="Web search").locator("button").click()
                await page.locator(".local-studio-compose-row textarea").fill("UI search smoke: summarize one technology headline")
                await page.locator(".local-studio-compose-row button.send").click()
                await page.wait_for_function("Alpine.$data(document.body).localStudioBusy === false", timeout=420000)
                state = await page.evaluate(
                    "() => { const app = Alpine.$data(document.body); const msgs = app.localStudioActiveMessages || []; return msgs[msgs.length - 1] || {}; }"
                )
                assert state and (state.get("content") or state.get("error")), "no assistant/error rendered"
                log_text = server_log_text()
                assert "ResponseNotRead" not in log_text, "server log contains ResponseNotRead after UI search"
                assert "Exception in ASGI application" not in log_text, "server log contains ASGI exception after UI search"
                assert not console_errors, console_errors[-3:]
                await browser.close()
        except Exception as exc:  # noqa: BLE001
            self.add("O-LS-03", "ui", "fail", safe_text(exc), started)
        else:
            self.add("O-LS-03", "ui", "pass", "OpenAI-compatible UI search stream ended in controlled UI state", started)

    def write_artifacts(self) -> None:
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        data = [asdict(item) for item in self.results]
        (self.artifacts_dir / "results.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        failed = [item for item in self.results if item.status == "fail"]
        skipped = [item for item in self.results if item.status == "skip"]
        lines = ["# Local Studio Real System Smoke Summary", "", f"Base URL: `{self.base_url}`", "", "## Results", ""]
        for item in self.results:
            lines.append(f"- `{item.status.upper()}` `{item.case_id}` ({item.layer}, {item.elapsed_ms}ms): {item.detail}")
        lines.extend(["", "## Outcome", ""])
        if failed:
            lines.append(f"Failed cases: {len(failed)}")
        else:
            lines.append("No failing cases in this smoke run.")
        if skipped:
            lines.append(f"Skipped cases: {len(skipped)}")
        (self.artifacts_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def pick_model(models: list[dict[str, Any]], prefixes: list[str]) -> str:
    ids = [str(model.get("id") or model.get("name") or "").removeprefix("models/") for model in models]
    ids = [model_id for model_id in ids if model_id]
    for prefix in prefixes:
        for model_id in ids:
            if model_id.lower().startswith(prefix.lower()) or prefix.lower() in model_id.lower():
                return model_id
    if not ids:
        raise AssertionError("no selectable model ids")
    return ids[0]


def latest_completed(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get("type") == "local_studio.completed":
            return event
    return None


def server_log_text() -> str:
    path = Path(os.environ.get("SERVER_LOG", ""))
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[-200_000:]


def load_openai_provider(base_url_override: str | None = None) -> dict[str, str]:
    key_path = Path(os.environ.get("OPENAI_COMPAT_KEY_FILE", "/mnt/c/Users/bamboo/Documents/github/key.txt"))
    raw = key_path.read_text(encoding="utf-8").strip()
    base_url = base_url_override or os.environ.get("OPENAI_COMPAT_BASE_URL", "").strip()
    token = os.environ.get("OPENAI_COMPAT_API_KEY", "").strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            base_url = base_url or str(data.get("base_url") or data.get("baseUrl") or data.get("url") or "").strip()
            token = token or str(data.get("api_key") or data.get("apiKey") or data.get("token") or "").strip()
    except ValueError:
        pass
    if not token:
        kv: dict[str, str] = {}
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        for line in lines:
            if "=" in line:
                key, value = line.split("=", 1)
                kv[key.strip().lower()] = value.strip().strip('"').strip("'")
        base_url = base_url or kv.get("base_url") or kv.get("openai_base_url") or kv.get("url") or ""
        token = token or kv.get("api_key") or kv.get("openai_api_key") or kv.get("token") or ""
        if not token and lines:
            urls = [line for line in lines if line.startswith(("http://", "https://"))]
            non_urls = [line for line in lines if not line.startswith(("http://", "https://")) and "=" not in line]
            base_url = base_url or (urls[0] if urls else "")
            token = non_urls[0] if non_urls else lines[0]
    base_url = base_url or "https://api.65535.space/v1"
    if not token:
        raise AssertionError(f"OpenAI-compatible token not found at {key_path}")
    if "\n" in token or "\r" in token:
        raise AssertionError("OpenAI-compatible token must be a single line")
    return {"base_url": base_url.rstrip("/"), "api_key": token}


def safe_text(value: Any) -> str:
    text = str(value)
    if not text and isinstance(value, BaseException):
        text = f"{type(value).__name__}: {value!r}"
    elif not text:
        text = repr(value)
    token = os.environ.get("OPENAI_COMPAT_API_KEY", "")
    if token:
        text = text.replace(token, "***")
    text = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer ***", text)
    text = re.sub(r"sk-[A-Za-z0-9._\-]+", "sk-***", text)
    return text[-1200:]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--artifacts-dir", required=True)
    args = parser.parse_args()

    runner = Runner(args.base_url, Path(args.artifacts_dir))
    try:
        await runner.run_boot()
        google_model = await runner.run_google_api()
        openai_base_url, openai_model = await runner.run_openai_api()
        await runner.run_ui(google_model, openai_base_url, openai_model)
    finally:
        await runner.close()
        runner.write_artifacts()
    return 1 if any(item.status == "fail" for item in runner.results) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))