from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_real_system_smoke import choose_model, compact_error, read_openai_config, request_json, stream_chat  # noqa: E402


def cache_status(result: dict[str, Any]) -> bool | None:
    data = result.get("data") if isinstance(result.get("data"), dict) else result
    cache = data.get("cache") if isinstance(data, dict) else None
    if isinstance(cache, dict):
        return bool(cache.get("hit"))
    return None


async def local_chat_case(
    client: httpx.AsyncClient,
    *,
    provider: dict[str, Any],
    mode: str,
    model: str,
    message: str,
    stream: bool,
    search: bool = False,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged_options = {"stream": stream, "search": search, "cache_enabled": True, "cache_namespace": f"matrix-{int(time.time())}-{mode}-{stream}-{search}"}
    if options:
        merged_options.update(options)
    payload = {**provider, "interface_mode": mode, "model": model, "message": message, "options": merged_options}
    if stream:
        return await stream_chat(client, payload)
    result = await request_json(client, "POST", "/api/local-studio/chat", json_body=payload)
    if result["status"] >= 400:
        result["error"] = compact_error(result.get("data"))
    return result


async def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--openai-key-file", default="/mnt/c/Users/bamboo/Documents/github/key.txt")
    args = parser.parse_args()

    artifacts = Path(args.run_root) / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    openai_base_url, openai_token, openai_meta = read_openai_config(Path(args.openai_key_file))
    timeout = httpx.Timeout(480.0, connect=30.0)
    results: dict[str, Any] = {"openai_key_file_meta": openai_meta, "cases": {}, "failures": []}
    run_id = f"matrix-{int(time.time())}"

    async with httpx.AsyncClient(base_url=args.base_url, timeout=timeout) as client:
        await request_json(client, "PUT", "/request-logs/status", json_body={"enabled": True})
        google_provider = {"provider_type": "google-ai-studio", "timeout": 300}
        openai_provider = {"provider_type": "openai", "base_url": openai_base_url, "api_key": openai_token, "timeout": 180}

        google_models_by_mode: dict[str, str] = {}
        google_image_model = "gemini-3.1-flash-image-preview"
        for mode in ("responses", "gemini", "openai", "claude"):
            model_result = await request_json(client, "POST", "/api/local-studio/models", json_body={**google_provider, "interface_mode": mode})
            results["cases"][f"G-models-{mode}"] = {"status": model_result["status"], "text_model_count": len(model_result["data"].get("data", [])), "image_model_count": len(model_result["data"].get("image_models", []))}
            google_models_by_mode[mode] = choose_model(model_result["data"].get("data", []), ("gemini-3-flash-preview", "gemini"))
            if mode == "responses" and model_result["data"].get("image_models"):
                google_image_model = choose_model(model_result["data"].get("image_models", []), ("gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview"))

        for mode, model in google_models_by_mode.items():
            for stream in (False, True):
                for search in (False, True):
                    name = f"G-{mode}-stream-{stream}-search-{search}"
                    results["cases"][name] = await local_chat_case(
                        client,
                        provider=google_provider,
                        mode=mode,
                        model=model,
                        message="Reply exactly ok. Do not use optional tools unless required.",
                        stream=stream,
                        search=search,
                    )

        image_tool_payload = {
            **google_provider,
            "interface_mode": "responses",
            "model": google_models_by_mode["responses"],
            "message": "Create a simple blue square icon as an image.",
            "options": {
                "stream": True,
                "search": True,
                "image_tool_enabled": True,
                "image_tool_provider": "google-ai-studio",
                "image_model": google_image_model,
                "size": "512x512",
                "cache_enabled": True,
                "cache_namespace": f"{run_id}-google-image-tool",
            },
        }
        results["cases"]["BUG-GEMINI-IMAGE-TOOL-01"] = await stream_chat(client, image_tool_payload)

        openai_models_by_mode: dict[str, str] = {}
        for mode in ("responses", "openai", "claude", "gemini"):
            model_result = await request_json(client, "POST", "/api/local-studio/models", json_body={**openai_provider, "interface_mode": mode})
            results["cases"][f"O-models-{mode}"] = {"status": model_result["status"], "text_model_count": len(model_result["data"].get("data", [])), "image_model_count": len(model_result["data"].get("image_models", [])), "error": None if model_result["ok"] else compact_error(model_result["data"])}
            if model_result["ok"] and model_result["data"].get("data"):
                openai_models_by_mode[mode] = choose_model(model_result["data"].get("data", []), ("gpt-5", "gpt-4.1", "gpt-4o", "gpt"))
            elif model_result["ok"]:
                results["cases"][f"O-models-{mode}"]["compatibility"] = "not_applicable_no_chat_models"

        for mode in ("responses", "openai"):
            model = openai_models_by_mode.get(mode)
            if not model:
                continue
            for stream in (False, True):
                for search in (False, True):
                    name = f"O-{mode}-stream-{stream}-search-{search}"
                    results["cases"][name] = await local_chat_case(
                        client,
                        provider=openai_provider,
                        mode=mode,
                        model=model,
                        message="Reply exactly ok. Do not use optional tools unless required.",
                        stream=stream,
                        search=search,
                    )

        for mode in ("claude", "gemini"):
            model = openai_models_by_mode.get(mode) or openai_models_by_mode.get("responses")
            if not model:
                continue
            for stream in (False, True):
                name = f"O-{mode}-compat-stream-{stream}"
                results["cases"][name] = await local_chat_case(
                    client,
                    provider=openai_provider,
                    mode=mode,
                    model=model,
                    message="Reply exactly ok.",
                    stream=stream,
                    search=False,
                )

        cache_base = {
            **openai_provider,
            "interface_mode": "responses",
            "model": openai_models_by_mode.get("responses"),
            "message": "Reply exactly cache-ok",
        }
        if cache_base["model"]:
            cache_payloads = {
                "first": {"stream": False, "cache_enabled": True, "cache_namespace": f"{run_id}-cache-a"},
                "repeat": {"stream": False, "cache_enabled": True, "cache_namespace": f"{run_id}-cache-a"},
                "namespace_miss": {"stream": False, "cache_enabled": True, "cache_namespace": f"{run_id}-cache-b"},
                "search_miss": {"stream": False, "search": True, "cache_enabled": True, "cache_namespace": f"{run_id}-cache-a"},
                "reasoning_miss": {"stream": False, "reasoning_effort": "high", "reasoning_summary": "auto", "cache_enabled": True, "cache_namespace": f"{run_id}-cache-a"},
                "repeat_after_misses": {"stream": False, "cache_enabled": True, "cache_namespace": f"{run_id}-cache-a"},
            }
            cache_hits: dict[str, bool | None] = {}
            for label, options in cache_payloads.items():
                result = await request_json(client, "POST", "/api/local-studio/chat", json_body={**cache_base, "options": options})
                results["cases"][f"CACHE-{label}"] = result
                cache_hits[label] = cache_status(result)
            results["cache_isolation"] = cache_hits

        base_model = google_models_by_mode["responses"]
        results["cases"]["BASE-chat-completions"] = await request_json(client, "POST", "/v1/chat/completions", json_body={"model": base_model, "messages": [{"role": "user", "content": "Reply exactly ok"}]})
        results["cases"]["BASE-responses"] = await request_json(client, "POST", "/v1/responses", json_body={"model": base_model, "input": "Reply exactly ok"})
        results["cases"]["BASE-messages"] = await request_json(client, "POST", "/v1/messages", json_body={"model": base_model, "messages": [{"role": "user", "content": "Reply exactly ok"}], "max_tokens": 64})
        results["cases"]["BASE-gemini-generateContent"] = await request_json(client, "POST", f"/v1beta/models/{base_model}:generateContent", json_body={"contents": [{"role": "user", "parts": [{"text": "Reply exactly ok"}]}]})
        results["cases"]["BASE-images-generations"] = await request_json(client, "POST", "/v1/images/generations", json_body={"model": google_image_model, "prompt": "simple blue square icon", "n": 1, "size": "512x512", "response_format": "url", "timeout": 240})
        image_data = results["cases"]["BASE-images-generations"].get("data", {}).get("data", [])
        if isinstance(image_data, list) and image_data and isinstance(image_data[0], dict) and image_data[0].get("url"):
            asset_url = image_data[0]["url"]
            asset_path = asset_url.replace(args.base_url, "") if asset_url.startswith(args.base_url) else asset_url
            asset = await client.get(asset_path)
            results["cases"]["BASE-image-asset"] = {"status": asset.status_code, "content_type": asset.headers.get("content-type", ""), "size": len(asset.content)}

        results["cases"]["FINAL-health"] = await request_json(client, "GET", "/api/local-studio/health")
        results["cases"]["FINAL-request-log-status"] = await request_json(client, "GET", "/request-logs/status")

        listing = await request_json(client, "GET", "/request-logs?limit=500")
        group_ids = [item.get("id") for item in listing["data"].get("data", []) if item.get("id")]
        exported = await request_json(client, "POST", "/request-logs/export", json_body={"ids": group_ids})
        export_text = json.dumps(exported.get("data"), ensure_ascii=False)
        results["request_logs"] = {
            "group_count": len(group_ids),
            "secret_redacted": openai_token not in export_text,
            "contains_response_not_read": "ResponseNotRead" in export_text,
            "contains_asgi_exception": "Exception in ASGI application" in export_text or "ExceptionGroup" in export_text,
            "contains_google_tool_config_error": "include_server_side_tool_invocations" in export_text,
            "contains_preview_tool_unsupported": "Unsupported tool type: web_search_preview" in export_text,
            "google_preview_seen": "web_search_preview" in export_text,
            "openai_web_search_seen": '"type":"web_search"' in export_text or '"type": "web_search"' in export_text,
        }

    for name, result in results["cases"].items():
        if not isinstance(result, dict):
            continue
        status = result.get("status")
        if isinstance(status, int) and status >= 500:
            results["failures"].append(f"{name}: status {status}")
        for key, label in (
            ("raw_contains_response_not_read", "ResponseNotRead"),
            ("raw_contains_preview_tool_error", "web_search_preview unsupported"),
            ("raw_contains_google_image_tool_config_error", "Google image tool config"),
        ):
            if result.get(key):
                results["failures"].append(f"{name}: {label}")
    cache_hits = results.get("cache_isolation", {})
    expected_cache = {
        "first": False,
        "repeat": True,
        "namespace_miss": False,
        "search_miss": False,
        "reasoning_miss": False,
        "repeat_after_misses": True,
    }
    for key, expected in expected_cache.items():
        if cache_hits.get(key) is not expected:
            results["failures"].append(f"cache {key}: expected {expected}, got {cache_hits.get(key)}")
    logs = results.get("request_logs", {})
    if not logs.get("secret_redacted"):
        results["failures"].append("request logs leaked OpenAI token")
    if logs.get("contains_response_not_read") or logs.get("contains_asgi_exception") or logs.get("contains_google_tool_config_error") or logs.get("contains_preview_tool_unsupported"):
        results["failures"].append("request logs contain P0 regression signature")

    output = artifacts / "matrix-results.json"
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"run_root": args.run_root, "case_count": len(results["cases"]), "failures": results["failures"], "cache_isolation": results.get("cache_isolation"), "request_logs": results.get("request_logs")}
    (artifacts / "matrix-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if results["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(run())
