from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx


def now_ms() -> int:
    return int(time.time() * 1000)


def compact_error(value: Any) -> str:
    if isinstance(value, dict):
        detail = value.get("detail")
        if isinstance(detail, dict):
            return str(detail.get("message") or detail)
        if detail:
            return str(detail)
        error = value.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error)
    return str(value)[:500]


def choose_model(models: list[dict[str, Any]], preferred: tuple[str, ...] = ()) -> str:
    ids = [str(item.get("id") or item.get("name") or "").replace("models/", "") for item in models]
    ids = [model_id for model_id in ids if model_id]
    for wanted in preferred:
        for model_id in ids:
            if model_id == wanted:
                return model_id
        for model_id in ids:
            if wanted in model_id:
                return model_id
    if not ids:
        raise RuntimeError("No model candidates returned")
    return ids[0]


def read_openai_config(path: Path) -> tuple[str, str, dict[str, Any]]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").replace("\r", "").split("\n") if line.strip()]
    if len(lines) >= 2 and lines[0].startswith(("http://", "https://")):
        base_url, token = lines[0].rstrip("/"), lines[1]
    elif len(lines) == 1:
        base_url, token = "https://api.openai.com/v1", lines[0]
    else:
        raise RuntimeError("OpenAI-compatible key file must contain token or base URL plus token")
    meta = {"line_count": len(lines), "base_url_length": len(base_url), "token_length": len(token)}
    return base_url, token, meta


async def request_json(client: httpx.AsyncClient, method: str, path: str, *, json_body: Any | None = None) -> dict[str, Any]:
    started = now_ms()
    response = await client.request(method, path, json=json_body)
    elapsed_ms = now_ms() - started
    try:
        data = response.json()
    except ValueError:
        data = {"raw": response.text[:1000]}
    return {"status": response.status_code, "elapsed_ms": elapsed_ms, "data": data, "ok": response.status_code < 400}


async def stream_chat(client: httpx.AsyncClient, payload: dict[str, Any]) -> dict[str, Any]:
    started = now_ms()
    events: list[dict[str, Any]] = []
    raw_parts: list[str] = []
    async with client.stream("POST", "/api/local-studio/chat", json=payload) as response:
        async for line in response.aiter_lines():
            raw_parts.append(line)
            if not line.startswith("data: "):
                continue
            text = line[6:].strip()
            if not text or text == "[DONE]":
                continue
            try:
                events.append(json.loads(text))
            except ValueError:
                events.append({"type": "parse_error", "raw": text[:500]})
    raw_text = "\n".join(raw_parts)
    completed = [event for event in events if event.get("type") == "local_studio.completed"]
    errors = [event for event in events if event.get("type") == "error" or event.get("error")]
    last_assistant: dict[str, Any] = {}
    if completed:
        conversation = completed[-1].get("conversation") if isinstance(completed[-1].get("conversation"), dict) else {}
        messages = conversation.get("messages") if isinstance(conversation.get("messages"), list) else []
        if messages and isinstance(messages[-1], dict):
            last_assistant = messages[-1]
    return {
        "status": response.status_code,
        "elapsed_ms": now_ms() - started,
        "event_types": [str(event.get("type") or "") for event in events],
        "error_count": len(errors),
        "raw_contains_response_not_read": "ResponseNotRead" in raw_text,
        "raw_contains_preview_tool_error": "Unsupported tool type: web_search_preview" in raw_text,
        "raw_contains_google_image_tool_config_error": "include_server_side_tool_invocations" in raw_text,
        "assistant_content_preview": str(last_assistant.get("content") or "")[:200],
        "assistant_error_preview": str(last_assistant.get("error") or "")[:300],
        "assistant_image_count": len(last_assistant.get("images") or []) if isinstance(last_assistant.get("images"), list) else 0,
        "assistant_has_thinking": bool(last_assistant.get("thinking")),
        "completed": bool(completed),
    }


def request_log_entries(exported: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for group in exported.get("data", []):
        for entry in group.get("entries", []):
            if isinstance(entry, dict):
                entry = dict(entry)
                entry["group_id"] = group.get("id")
                entries.append(entry)
    return entries


def body_text(entry: dict[str, Any]) -> str:
    for key in ("body_raw", "body", "response_body_raw"):
        value = entry.get(key)
        if isinstance(value, str) and value:
            return value
    value = entry.get("body_json")
    if value is not None:
        return json.dumps(value, ensure_ascii=False)
    return ""


async def run_ui(base_url: str, artifacts: Path) -> dict[str, Any]:
    from playwright.async_api import async_playwright

    ui_result: dict[str, Any] = {"routes": [], "console_errors": [], "page_errors": [], "local_studio_send": {}}
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 1100})
        page.on("console", lambda message: ui_result["console_errors"].append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: ui_result["page_errors"].append(str(error)))
        for route in ("#studio", "#chat", "#images", "#requests", "#accounts"):
            started = now_ms()
            await page.goto(f"{base_url}/static/index.html{route}", wait_until="domcontentloaded", timeout=60000)
            await page.screenshot(path=str(artifacts / "screenshots" / f"route-{route[1:]}.png"), full_page=True)
            body = await page.locator("body").inner_text(timeout=30000)
            ui_result["routes"].append({"route": route, "elapsed_ms": now_ms() - started, "has_body": bool(body.strip()), "body_preview": body[:200]})

        await page.goto(f"{base_url}/static/index.html#studio", wait_until="domcontentloaded", timeout=60000)
        await page.get_by_role("button", name="加载模型").click(timeout=30000)
        await page.wait_for_function(
            "() => document.body.innerText.includes('gemini-3-flash-preview') && !document.body.innerText.includes('等待模型')",
            timeout=120000,
        )
        textbox = page.get_by_role("textbox", name="向 Local Studio 发送消息、图片或文件...")
        await textbox.fill("Reply exactly ok")
        await page.get_by_role("button", name="发送").click(timeout=30000)
        await page.wait_for_function("() => !document.body.innerText.includes('正在等待模型返回')", timeout=300000)
        body = await page.locator("body").inner_text(timeout=30000)
        await page.screenshot(path=str(artifacts / "screenshots" / "local-studio-send-complete.png"), full_page=True)
        ui_result["local_studio_send"] = {
            "completed": "Local Studio 流式响应完成" in body or "Assistant" in body,
            "has_pending_residue": "正在等待模型返回" in body,
            "has_assistant": "Assistant" in body,
            "has_error_text": "ResponseNotRead" in body or "ExceptionGroup" in body or "Exception in ASGI application" in body,
        }
        await browser.close()
    return ui_result


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--openai-key-file", default="/mnt/c/Users/bamboo/Documents/github/key.txt")
    parser.add_argument("--skip-ui", action="store_true")
    args = parser.parse_args()

    artifacts = Path(args.run_root) / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "screenshots").mkdir(parents=True, exist_ok=True)
    openai_base_url, openai_token, openai_meta = read_openai_config(Path(args.openai_key_file))
    run_id = f"smoke-{int(time.time())}"
    api_results: dict[str, Any] = {"openai_key_file_meta": openai_meta, "cases": {}}
    contracts: dict[str, Any] = {"cases": {}}

    timeout = httpx.Timeout(360.0, connect=30.0)
    async with httpx.AsyncClient(base_url=args.base_url, timeout=timeout) as client:
        api_results["cases"]["BOOT-health"] = await request_json(client, "GET", "/api/local-studio/health")
        api_results["cases"]["BOOT-request-log-enable"] = await request_json(client, "PUT", "/request-logs/status", json_body={"enabled": True})
        api_results["cases"]["BOOT-v1-models"] = await request_json(client, "GET", "/v1/models")
        api_results["cases"]["BOOT-v1beta-models"] = await request_json(client, "GET", "/v1beta/models")

        google_models = await request_json(client, "POST", "/api/local-studio/models", json_body={"provider_type": "google-ai-studio", "interface_mode": "responses"})
        api_results["cases"]["G-models-responses"] = {"status": google_models["status"], "elapsed_ms": google_models["elapsed_ms"], "text_model_count": len(google_models["data"].get("data", [])), "image_model_count": len(google_models["data"].get("image_models", []))}
        google_model = choose_model(google_models["data"].get("data", []), ("gemini-3-flash-preview", "gemini"))
        google_image_models = google_models["data"].get("image_models", [])
        google_image_model = choose_model(google_image_models, ("gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview")) if google_image_models else "gemini-3.1-flash-image-preview"

        google_text_payload = {
            "provider_type": "google-ai-studio",
            "interface_mode": "responses",
            "model": google_model,
            "message": "Reply exactly ok",
            "options": {"stream": True, "cache_enabled": True, "cache_namespace": f"api-smoke-google-text-{run_id}"},
        }
        api_results["cases"]["G-LS-01-stream-text"] = await stream_chat(client, google_text_payload)
        google_cache_payload = dict(google_text_payload)
        google_cache_payload["options"] = {"stream": False, "cache_enabled": True, "cache_namespace": f"api-smoke-google-text-{run_id}"}
        api_results["cases"]["G-LS-02-cache-repeat"] = await request_json(client, "POST", "/api/local-studio/chat", json_body=google_cache_payload)

        google_tools_payload = {
            "provider_type": "google-ai-studio",
            "interface_mode": "responses",
            "model": google_model,
            "message": "Do not search and do not draw. Reply with plain text ok.",
            "options": {
                "stream": True,
                "search": True,
                "image_tool_enabled": True,
                "image_tool_provider": "google-ai-studio",
                "image_model": google_image_model,
                "size": "1024x1024",
                "cache_enabled": True,
                "cache_namespace": f"api-smoke-google-tools-optional-{run_id}",
            },
        }
        api_results["cases"]["G-LS-05-tools-optional"] = await stream_chat(client, google_tools_payload)

        openai_models = await request_json(
            client,
            "POST",
            "/api/local-studio/models",
            json_body={"provider_type": "openai", "base_url": openai_base_url, "api_key": openai_token, "interface_mode": "responses", "timeout": 180},
        )
        api_results["cases"]["O-LS-01-models"] = {"status": openai_models["status"], "elapsed_ms": openai_models["elapsed_ms"], "text_model_count": len(openai_models["data"].get("data", [])), "image_model_count": len(openai_models["data"].get("image_models", [])), "error": None if openai_models["ok"] else compact_error(openai_models["data"])}
        openai_model = choose_model(openai_models["data"].get("data", []), ("gpt-5", "gpt-4.1", "gpt-4o", "gpt"))

        openai_text_payload = {
            "provider_type": "openai",
            "base_url": openai_base_url,
            "api_key": openai_token,
            "interface_mode": "responses",
            "model": openai_model,
            "message": "Reply exactly ok",
            "options": {"stream": True, "cache_enabled": True, "cache_namespace": f"api-smoke-openai-text-{run_id}"},
        }
        api_results["cases"]["O-LS-02-stream-text"] = await stream_chat(client, openai_text_payload)

        openai_search_payload = {
            "provider_type": "openai",
            "base_url": openai_base_url,
            "api_key": openai_token,
            "interface_mode": "responses",
            "model": openai_model,
            "message": "Search for one current technology news item and summarize it in one sentence.",
            "options": {"stream": True, "search": True, "cache_enabled": True, "cache_namespace": f"api-smoke-openai-search-{run_id}"},
        }
        api_results["cases"]["O-LS-03-search-stream"] = await stream_chat(client, openai_search_payload)

        openai_reasoning_payload = {
            "provider_type": "openai",
            "base_url": openai_base_url,
            "api_key": openai_token,
            "interface_mode": "responses",
            "model": openai_model,
            "message": "Decide whether 17*23 is greater than 390. Give a brief conclusion.",
            "options": {"stream": True, "reasoning_effort": "high", "reasoning_summary": "auto", "cache_enabled": True, "cache_namespace": f"api-smoke-openai-reasoning-{run_id}"},
        }
        api_results["cases"]["O-LS-06-reasoning-stream"] = await stream_chat(client, openai_reasoning_payload)
        openai_reasoning_payload_nonstream = dict(openai_reasoning_payload)
        openai_reasoning_payload_nonstream["options"] = dict(openai_reasoning_payload["options"], stream=False, cache_namespace=f"api-smoke-openai-reasoning-nonstream-{run_id}")
        api_results["cases"]["API-LS-08-reasoning-nonstream"] = await request_json(client, "POST", "/api/local-studio/chat", json_body=openai_reasoning_payload_nonstream)

        api_results["cases"]["BASE-v1-responses"] = await request_json(client, "POST", "/v1/responses", json_body={"model": google_model, "input": "Reply exactly ok"})
        api_results["cases"]["FINAL-health"] = await request_json(client, "GET", "/api/local-studio/health")
        api_results["cases"]["FINAL-log-status"] = await request_json(client, "GET", "/request-logs/status")

        listing = await request_json(client, "GET", "/request-logs?limit=200")
        group_ids = [item.get("id") for item in listing["data"].get("data", []) if item.get("id")]
        exported = await request_json(client, "POST", "/request-logs/export", json_body={"ids": group_ids})
        entries = request_log_entries(exported["data"] if isinstance(exported["data"], dict) else {})
        export_text = json.dumps(exported["data"], ensure_ascii=False)
        api_results["request_logs"] = {
            "group_count": len(group_ids),
            "entry_count": len(entries),
            "secret_redacted": openai_token not in export_text,
            "contains_response_not_read": "ResponseNotRead" in export_text,
            "contains_asgi_exception": "Exception in ASGI application" in export_text or "ExceptionGroup" in export_text,
            "contains_preview_tool_unsupported": "Unsupported tool type: web_search_preview" in export_text,
        }
        upstream_request_bodies = [body_text(entry) for entry in entries if entry.get("phase") == "upstream_request"]
        google_bodies = [body for body in upstream_request_bodies if "google-ai-studio" in body or "web_search_preview" in body]
        openai_bodies = [body for body in upstream_request_bodies if "web_search" in body and openai_base_url not in body]
        contracts["cases"]["provider-aware-search-tools"] = {
            "google_uses_web_search_preview": any("web_search_preview" in body for body in google_bodies),
            "openai_uses_web_search": any('"type":"web_search"' in body or '"type": "web_search"' in body for body in upstream_request_bodies),
            "openai_has_no_web_search_preview": not any("web_search_preview" in body and "Search for one current technology" in body for body in upstream_request_bodies),
        }
        contracts["cases"]["request-log-lifecycle"] = {
            "has_groups": bool(group_ids),
            "phases_seen": sorted({str(entry.get("phase") or "") for entry in entries}),
            "has_client_request": any(entry.get("phase") == "client_request" for entry in entries),
            "has_upstream_request": any(entry.get("phase") == "upstream_request" for entry in entries),
            "has_upstream_response": any(entry.get("phase") == "upstream_response" for entry in entries),
            "has_client_response": any(entry.get("phase") == "client_response" for entry in entries),
            "secret_redacted": api_results["request_logs"]["secret_redacted"],
        }

    ui_results: dict[str, Any] = {"skipped": True}
    if not args.skip_ui:
        ui_results = await run_ui(args.base_url, artifacts)
        contracts["cases"]["frontend-state-machine"] = {
            "route_count": len(ui_results.get("routes", [])),
            "console_error_count": len(ui_results.get("console_errors", [])),
            "page_error_count": len(ui_results.get("page_errors", [])),
            "local_studio_send_completed": ui_results.get("local_studio_send", {}).get("completed"),
            "no_pending_residue": not ui_results.get("local_studio_send", {}).get("has_pending_residue"),
        }

    failures: list[str] = []
    for name, result in api_results["cases"].items():
        if isinstance(result, dict) and result.get("status", 200) >= 500:
            failures.append(f"{name}: status {result.get('status')}")
    for name in ("G-LS-01-stream-text", "G-LS-05-tools-optional", "O-LS-02-stream-text", "O-LS-03-search-stream", "O-LS-06-reasoning-stream"):
        result = api_results["cases"].get(name, {})
        if isinstance(result, dict):
            if result.get("raw_contains_response_not_read"):
                failures.append(f"{name}: leaked ResponseNotRead")
            if result.get("raw_contains_preview_tool_error"):
                failures.append(f"{name}: web_search_preview unsupported error")
            if result.get("raw_contains_google_image_tool_config_error"):
                failures.append(f"{name}: Google image tool config error")
            if not result.get("completed"):
                failures.append(f"{name}: missing local_studio.completed")
    if not api_results.get("request_logs", {}).get("secret_redacted", False):
        failures.append("request logs leaked OpenAI token")
    if ui_results.get("console_errors"):
        failures.append("UI console errors present")
    if ui_results.get("local_studio_send", {}).get("has_pending_residue"):
        failures.append("UI pending state residue after send")

    summary = {
        "base_url": args.base_url,
        "run_root": args.run_root,
        "failures": failures,
        "api_case_count": len(api_results["cases"]),
        "ui_route_count": len(ui_results.get("routes", [])) if isinstance(ui_results, dict) else 0,
    }
    (artifacts / "api-results.json").write_text(json.dumps(api_results, ensure_ascii=False, indent=2), encoding="utf-8")
    (artifacts / "ui-results.json").write_text(json.dumps(ui_results, ensure_ascii=False, indent=2), encoding="utf-8")
    (artifacts / "architecture-contract-results.json").write_text(json.dumps(contracts, ensure_ascii=False, indent=2), encoding="utf-8")
    (artifacts / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Real System Smoke Summary", "", f"Run root: `{args.run_root}`", f"API cases: {summary['api_case_count']}", f"UI routes: {summary['ui_route_count']}", ""]
    if failures:
        lines.append("## Failures")
        lines.extend(f"* {failure}" for failure in failures)
    else:
        lines.append("## Result")
        lines.append("* No smoke failures detected.")
    (artifacts / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
