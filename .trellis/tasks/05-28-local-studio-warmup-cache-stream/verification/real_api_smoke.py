import json
import time
from pathlib import Path

import httpx

BASE_URL = "http://127.0.0.1:8093"
OPENAI_KEY_PATH = Path("/mnt/c/Users/bamboo/Documents/github/key.txt")
ARTIFACTS = Path("/home/bamboo/aistudio-api-u1-realtest/artifacts")
ARTIFACTS.mkdir(parents=True, exist_ok=True)
RUN_ID = f"warmup-cache-stream-{int(time.time())}"


def fail(message, details=None):
    payload = {"ok": False, "message": message, "details": details or {}}
    (ARTIFACTS / "api_smoke_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    raise SystemExit(message)


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


def request_json(client, method, path, **kwargs):
    response = client.request(method, BASE_URL + path, **kwargs)
    if response.status_code >= 400:
        fail(f"{method} {path} failed", {"status": response.status_code, "body_prefix": response.text[:500].replace("\n", " ")})
    return response.json(), response


def wait_for_warmup(client):
    deadline = time.perf_counter() + 240
    last_warmup = None
    while time.perf_counter() < deadline:
        health, _ = request_json(client, "GET", "/health")
        warmup = health.get("warmup") if isinstance(health, dict) else None
        if not isinstance(warmup, dict):
            return {"status": "unknown"}
        last_warmup = warmup
        status = str(warmup.get("status") or "idle")
        if status in {"idle", "complete"}:
            return warmup
        if status in {"failed", "partial", "cancelled"}:
            fail("Browser warmup did not complete cleanly", {"warmup": warmup})
        time.sleep(1)
    fail("Timed out waiting for browser warmup completion", {"warmup": last_warmup})


def choose_model(models):
    ids = [str(item.get("id") or item.get("name") or "") for item in models if isinstance(item, dict)]
    for candidate in ["gpt-4.1-mini", "gpt-4o-mini", "gpt-4.1-nano", "o4-mini", "gpt-4o"]:
        if candidate in ids:
            return candidate
    for model_id in ids:
        lowered = model_id.lower()
        if model_id and "image" not in lowered and "audio" not in lowered and "embedding" not in lowered:
            return model_id
    fail("No usable OpenAI-compatible chat model returned", {"model_count": len(ids)})


def assistant_message(conversation):
    for message in reversed(conversation.get("messages") or []):
        if message.get("role") == "assistant":
            return message
    fail("Conversation has no assistant message")


def fetch_recent_groups(client, limit=30):
    data, _ = request_json(client, "GET", f"/request-logs?limit={limit}")
    groups = []
    for item in data.get("data", []):
        group, _ = request_json(client, "GET", f"/request-logs/groups/{item['id']}")
        groups.append(group)
    return groups


def group_contains(group, text):
    return text in json.dumps(group, ensure_ascii=False)


def group_phases(group):
    return [entry.get("phase") for entry in group.get("entries", [])]


def assert_no_secret(groups, token):
    for group in groups:
        if token and token in json.dumps(group, ensure_ascii=False):
            fail("Request logs leaked the OpenAI-compatible token", {"group": group.get("id")})


def local_studio_payload(base_url, token, model, prompt, stream=False):
    return {
        "provider_type": "openai",
        "base_url": base_url,
        "api_key": token,
        "interface_mode": "responses",
        "model": model,
        "message": prompt,
        "timeout": 180,
        "options": {
            "stream": stream,
            "search": False,
            "reasoning_effort": "off",
            "cache_enabled": True,
            "cache_namespace": RUN_ID,
        },
    }


def run_local_studio_repeated_prompt(client, base_url, token, model):
    prompt = f"Reply with exactly OK for api-repeat {RUN_ID}"
    payload = local_studio_payload(base_url, token, model, prompt, stream=False)
    first, _ = request_json(client, "POST", "/api/local-studio/chat", json=payload)
    second, _ = request_json(client, "POST", "/api/local-studio/chat", json=payload)
    for label, data in [("first", first), ("second", second)]:
        if "cache" in data:
            fail(f"{label} non-stream response still contains cache metadata")
        assistant = assistant_message(data.get("conversation") or {})
        if "cache" in assistant:
            fail(f"{label} assistant message still contains cache metadata")
        if not str(assistant.get("content") or "").strip():
            fail(f"{label} assistant message was empty")
    groups = [group for group in fetch_recent_groups(client) if group_contains(group, prompt)]
    upstream_groups = [group for group in groups if "upstream_request" in group_phases(group)]
    if len(upstream_groups) < 2:
        fail("Repeated prompt did not create two upstream request groups", {"matching_groups": len(groups), "upstream_groups": len(upstream_groups)})
    return {"matching_groups": len(groups), "upstream_groups": len(upstream_groups)}


def iter_sse_events(response):
    for line in response.iter_lines():
        if not line or not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload == "[DONE]":
            yield {"type": "done"}
            continue
        try:
            yield json.loads(payload)
        except json.JSONDecodeError:
            yield {"type": "raw", "data": payload}


def run_local_studio_stream(client, base_url, token, model):
    prompt = f"Stream three short words for api-stream {RUN_ID}"
    payload = local_studio_payload(base_url, token, model, prompt, stream=True)
    started = time.perf_counter()
    first_delta_seconds = None
    delta_count = 0
    completed = None
    with client.stream("POST", BASE_URL + "/api/local-studio/chat", json=payload, timeout=180) as response:
        if response.status_code >= 400:
            fail("Local Studio stream request failed", {"status": response.status_code, "body_prefix": response.read().decode(errors="ignore")[:500]})
        if response.headers.get("cache-control") != "no-cache":
            fail("Local Studio stream missing Cache-Control no-cache header", {"headers": dict(response.headers)})
        if response.headers.get("x-accel-buffering") != "no":
            fail("Local Studio stream missing X-Accel-Buffering no header", {"headers": dict(response.headers)})
        for event in iter_sse_events(response):
            event_type = event.get("type")
            if event_type == "local_studio.delta":
                delta_count += 1
                if first_delta_seconds is None and (event.get("content") or event.get("thinking")):
                    first_delta_seconds = time.perf_counter() - started
            elif event_type == "local_studio.completed":
                completed = event
                break
            elif event_type == "error" or event.get("error"):
                fail("Local Studio stream returned error event", {"event": event})
    if delta_count < 1 or first_delta_seconds is None:
        fail("Local Studio stream produced no visible delta before completion", {"delta_count": delta_count})
    if first_delta_seconds > 30:
        fail("Local Studio stream first delta was too slow", {"first_delta_seconds": round(first_delta_seconds, 3)})
    if not completed or "cache" in completed:
        fail("Local Studio stream completed event missing or contains cache metadata")
    assistant = assistant_message(completed.get("conversation") or {})
    if "cache" in assistant:
        fail("Local Studio stream assistant contains cache metadata")
    return {"delta_count": delta_count, "first_delta_seconds": round(first_delta_seconds, 3)}


def run_browser_backed_warm_stream(client):
    prompt = f"Reply exactly OK for warm stream {RUN_ID}"
    payload = {"model": "gemma-4-31b-it", "messages": [{"role": "user", "content": prompt}], "stream": True, "max_tokens": 32}
    started = time.perf_counter()
    first_chunk_seconds = None
    chunk_count = 0
    with client.stream("POST", BASE_URL + "/v1/chat/completions", json=payload, timeout=180) as response:
        if response.status_code >= 400:
            fail("Browser-backed Gemini stream request failed", {"status": response.status_code, "body_prefix": response.read().decode(errors="ignore")[:500]})
        for event in iter_sse_events(response):
            if event.get("type") == "done":
                break
            choices = event.get("choices") if isinstance(event, dict) else None
            if choices:
                chunk_count += 1
                delta = choices[0].get("delta") or {}
                if first_chunk_seconds is None and delta.get("content"):
                    first_chunk_seconds = time.perf_counter() - started
            if first_chunk_seconds is not None and chunk_count >= 1:
                break
    if first_chunk_seconds is None:
        fail("Browser-backed Gemini stream produced no text chunk", {"chunk_count": chunk_count})
    if first_chunk_seconds > 45:
        fail("Browser-backed Gemini first chunk exceeded warmup threshold", {"first_chunk_seconds": round(first_chunk_seconds, 3)})
    return {"chunk_count_before_break": chunk_count, "first_chunk_seconds": round(first_chunk_seconds, 3)}


def run_google_local_studio_stream(client):
    models_payload = {"provider_type": "google-ai-studio", "interface_mode": "responses", "timeout": 300}
    models_data, _ = request_json(client, "POST", "/api/local-studio/models", json=models_payload)
    model_ids = [str(item.get("id") or item.get("name") or "") for item in models_data.get("data") or [] if isinstance(item, dict)]
    model = next((item for item in ["gemma-4-31b-it", "gemini-3-flash-preview", "gemini-2.5-flash"] if item in model_ids), model_ids[0] if model_ids else "")
    if not model:
        fail("Google Local Studio model list did not return a usable model")
    prompt = f"Reply exactly OK for google local stream {RUN_ID}"
    payload = {
        "provider_type": "google-ai-studio",
        "interface_mode": "responses",
        "model": model,
        "message": prompt,
        "timeout": 300,
        "options": {"stream": True, "search": False, "reasoning_effort": "off"},
    }
    started = time.perf_counter()
    first_delta_seconds = None
    delta_count = 0
    completed = None
    with client.stream("POST", BASE_URL + "/api/local-studio/chat", json=payload, timeout=300) as response:
        if response.status_code >= 400:
            fail("Google Local Studio stream request failed", {"status": response.status_code, "body_prefix": response.read().decode(errors="ignore")[:500]})
        if response.headers.get("cache-control") != "no-cache" or response.headers.get("x-accel-buffering") != "no":
            fail("Google Local Studio stream missing no-buffer headers", {"headers": dict(response.headers)})
        for event in iter_sse_events(response):
            event_type = event.get("type")
            if event_type == "local_studio.delta":
                delta_count += 1
                if first_delta_seconds is None and (event.get("content") or event.get("thinking")):
                    first_delta_seconds = time.perf_counter() - started
            elif event_type == "local_studio.completed":
                completed = event
                break
            elif event_type == "error" or event.get("error"):
                fail("Google Local Studio stream returned error event", {"event": event})
    if first_delta_seconds is None or delta_count < 1:
        fail("Google Local Studio stream produced no visible delta", {"delta_count": delta_count})
    if first_delta_seconds > 45:
        fail("Google Local Studio first delta exceeded warmup threshold", {"first_delta_seconds": round(first_delta_seconds, 3)})
    if not completed or "cache" in completed:
        fail("Google Local Studio completed event missing or contains cache metadata")
    return {"model": model, "delta_count": delta_count, "first_delta_seconds": round(first_delta_seconds, 3)}


def main():
    base_url, token = read_openai_credentials()
    summary = {"ok": True, "run_id": RUN_ID}
    with httpx.Client(timeout=60) as client:
        for _ in range(60):
            try:
                request_json(client, "GET", "/health")
                request_json(client, "GET", "/api/local-studio/health")
                break
            except Exception:
                time.sleep(1)
        else:
            fail("Server health checks did not become ready")
        summary["warmup"] = wait_for_warmup(client)
        status, _ = request_json(client, "PUT", "/request-logs/status", json={"enabled": True})
        if not status.get("enabled"):
            fail("Request logs did not enable")
        models_payload = {"provider_type": "openai", "base_url": base_url, "api_key": token, "interface_mode": "responses", "timeout": 120}
        models_data, _ = request_json(client, "POST", "/api/local-studio/models", json=models_payload)
        model = choose_model(models_data.get("data") or [])
        summary["openai_model"] = model
        summary["repeated_prompt"] = run_local_studio_repeated_prompt(client, base_url, token, model)
        summary["local_studio_stream"] = run_local_studio_stream(client, base_url, token, model)
        summary["browser_backed_warm_stream"] = run_browser_backed_warm_stream(client)
        summary["google_local_studio_stream"] = run_google_local_studio_stream(client)
        groups = fetch_recent_groups(client, limit=50)
        assert_no_secret(groups, token)
        summary["request_log_groups_checked"] = len(groups)
    (ARTIFACTS / "api_smoke_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
