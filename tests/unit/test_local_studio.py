import asyncio
import json

import httpx
from fastapi import FastAPI

from aistudio_api.api import routes_local_studio
from aistudio_api.api.routes_local_studio import router as local_studio_router
from aistudio_api.config import settings
from aistudio_api.infrastructure.local_studio import (
    GPT_IMAGE_2_SIZE_OPTIONS,
    LocalStudioStore,
    build_local_studio_chat_payload,
    build_responses_payload,
    filter_chat_models,
    local_studio_chat_path,
    normalize_openai_base_url,
    parse_local_studio_output,
    parse_local_studio_stream_event,
    validate_gpt_image_2_size,
)


def request_app(app: FastAPI, method: str, url: str, **kwargs) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, url, **kwargs)

    return asyncio.run(send())


def local_studio_app(storage_dir):
    old_dir = settings.local_studio_dir
    settings.local_studio_dir = str(storage_dir)
    app = FastAPI()
    app.include_router(local_studio_router)
    return app, old_dir


def test_filter_chat_models_excludes_image_only_models():
    filtered = filter_chat_models(
        [
            {"id": "gpt-5.4-mini"},
            {"id": "gpt-image-2"},
            {"id": "GPT-IMAGE-1"},
            {"id": "gpt-4o-audio-preview"},
            {"id": "text-embedding-3-large"},
            {"name": "compatible-chat"},
        ]
    )

    assert [model["id"] for model in filtered] == ["gpt-5.4-mini", "compatible-chat"]


def test_local_studio_protocol_paths_payloads_and_parsers():
    messages = [{"role": "user", "content": "hello"}]

    assert local_studio_chat_path("openai", "gpt-test") == "/chat/completions"
    assert local_studio_chat_path("responses", "gpt-test") == "/responses"
    assert local_studio_chat_path("gemini", "gemini-test", stream=True) == "/models/gemini-test:streamGenerateContent"
    assert local_studio_chat_path("claude", "claude-test") == "/messages"

    openai_payload = build_local_studio_chat_payload(mode="openai", model="gpt-test", messages=messages, options={"stream": True, "max_tokens": 12, "reasoning_effort": "low"})
    responses_payload = build_local_studio_chat_payload(mode="responses", model="gpt-test", messages=messages, options={"stream": True})
    gemini_payload = build_local_studio_chat_payload(mode="gemini", model="gemini-test", messages=messages, options={"stream": True, "reasoning_effort": "medium"})
    claude_payload = build_local_studio_chat_payload(mode="claude", model="claude-test", messages=messages, options={"stream": True, "max_tokens": 12, "reasoning_effort": "high"})

    assert openai_payload["messages"] == [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
    assert openai_payload["stream"] is True
    assert openai_payload["thinking"] == "low"
    assert responses_payload["input"] == [{"role": "user", "content": [{"type": "input_text", "text": "hello"}]}]
    assert responses_payload["stream"] is True
    assert gemini_payload["contents"] == [{"role": "user", "parts": [{"text": "hello"}]}]
    assert gemini_payload["generationConfig"]["thinkingConfig"] == [1, None, None, 2]
    assert claude_payload["messages"] == [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
    assert claude_payload["max_tokens"] == 12
    assert claude_payload["thinking"] == "high"

    assert parse_local_studio_output("openai", {"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 2}})["content"] == "ok"
    assert parse_local_studio_output("responses", {"output_text": "ok"})["content"] == "ok"
    assert parse_local_studio_output("gemini", {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})["content"] == "ok"
    assert parse_local_studio_output("claude", {"content": [{"type": "text", "text": "ok"}]})["content"] == "ok"


def test_local_studio_conversation_routes_round_trip_and_bulk_delete(tmp_path):
    app, old_dir = local_studio_app(tmp_path)
    try:
        created = request_app(app, "POST", "/api/local-studio/conversations", json={"title": "Draft", "model": "gpt-5.4-mini", "interface_mode": "claude"})
        assert created.status_code == 200
        conversation = created.json()

        patched = request_app(app, "PATCH", f"/api/local-studio/conversations/{conversation['id']}", json={"title": "Renamed"})
        listed = request_app(app, "GET", "/api/local-studio/conversations")
        fetched = request_app(app, "GET", f"/api/local-studio/conversations/{conversation['id']}")
        deleted = request_app(app, "POST", "/api/local-studio/conversations/bulk-delete", json={"ids": [conversation["id"], "missing"]})
        missing = request_app(app, "GET", f"/api/local-studio/conversations/{conversation['id']}")

        assert patched.json()["title"] == "Renamed"
        assert patched.json()["interface_mode"] == "claude"
        assert listed.json()["data"][0]["title"] == "Renamed"
        assert listed.json()["data"][0]["interface_mode"] == "claude"
        assert fetched.json()["model"] == "gpt-5.4-mini"
        assert fetched.json()["interface_mode"] == "claude"
        assert deleted.json()["deleted"] == [conversation["id"]]
        assert deleted.json()["missing"] == ["missing"]
        assert missing.status_code == 404
    finally:
        settings.local_studio_dir = old_dir


def test_model_route_rejects_multiline_token_without_leaking_value(tmp_path):
    app, old_dir = local_studio_app(tmp_path)
    secret = "sk-test-secret"
    try:
        response = request_app(
            app,
            "POST",
            "/api/local-studio/models",
            json={"base_url": "https://api.openai.com/v1", "api_key": f"{secret}\nextra"},
        )
    finally:
        settings.local_studio_dir = old_dir

    body = response.json()
    assert response.status_code == 400
    assert body["detail"]["message"] == "API token must be a single line"
    assert secret not in str(body)


def test_build_responses_payload_includes_attachments_reasoning_and_image_tool():
    payload = build_responses_payload(
        model="gpt-5.4-mini",
        messages=[
            {
                "role": "user",
                "content": "Describe these files",
                "attachments": [
                    {"name": "cat.png", "mime": "image/png", "path": "cat.png"},
                    {"name": "notes.pdf", "mime": "application/pdf", "path": "notes.pdf"},
                ],
            }
        ],
        options={
            "reasoning_effort": "high",
            "reasoning_summary": "auto",
            "image_tool_enabled": True,
            "size": "1024x1024",
            "quality": "high",
            "background": "transparent",
            "output_format": "png",
            "output_compression": 80,
        },
        asset_resolver=lambda asset: f"data:{asset['mime']};base64,ZmFrZQ==",
    )

    content = payload["input"][0]["content"]
    assert payload["model"] == "gpt-5.4-mini"
    assert payload["reasoning"] == {"effort": "high", "summary": "auto"}
    assert content[0] == {"type": "input_text", "text": "Describe these files"}
    assert content[1]["type"] == "input_image"
    assert content[2]["type"] == "input_file"
    assert payload["tools"] == [
        {
            "type": "image_generation",
            "model": "gpt-image-2",
            "size": "1024x1024",
            "quality": "high",
            "background": "transparent",
            "output_format": "png",
            "output_compression": 80,
        }
    ]


def test_gpt_image_2_size_options_match_official_constraints():
    sizes = [item["size"] for item in GPT_IMAGE_2_SIZE_OPTIONS]

    assert sizes == ["1024x1024", "1024x1536", "1536x1024", "1536x864", "2560x1440", "3824x2144"]
    assert "3840x2160" not in sizes
    assert [validate_gpt_image_2_size(size) for size in sizes] == sizes


def test_gpt_image_2_size_validation_rejects_invalid_constraints():
    invalid_sizes = ["3840x2160", "1000x1000", "4096x1024", "1024x320", "640x640"]

    for size in invalid_sizes:
        try:
            validate_gpt_image_2_size(size)
        except ValueError:
            continue
        raise AssertionError(f"expected {size} to be invalid")


def test_chat_route_posts_responses_payload_and_persists_reply(tmp_path, monkeypatch):
    app, old_dir = local_studio_app(tmp_path)
    captured = {}

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "application/json"}
        content = b'{"id":"resp_1","output_text":"hello from upstream","usage":{"input_tokens":3,"output_tokens":4}}'

        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "resp_1", "output_text": "hello from upstream", "usage": {"input_tokens": 3, "output_tokens": 4}}

    class FakeClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(routes_local_studio, "_new_http_client", FakeClient)
    try:
        response = request_app(
            app,
            "POST",
            "/api/local-studio/chat",
            json={
                "base_url": "http://compat.example/v1",
                "api_key": "token-1",
                "timeout": 45,
                "model": "gpt-5.4-mini",
                "message": "hello",
                "options": {"reasoning_effort": "low", "reasoning_summary": "auto"},
            },
        )
    finally:
        settings.local_studio_dir = old_dir

    assert response.status_code == 200
    body = response.json()
    assert captured["timeout"] == 45
    assert captured["url"] == "http://compat.example/v1/responses"
    assert captured["headers"]["Authorization"] == "Bearer token-1"
    assert captured["json"]["input"][0] == {"role": "user", "content": [{"type": "input_text", "text": "hello"}]}
    assert body["conversation"]["messages"][-1]["content"] == "hello from upstream"
    assert body["conversation"]["messages"][-1]["usage"]["input_tokens"] == 3


def test_chat_route_posts_selected_interface_mode_and_timeout(tmp_path, monkeypatch):
    app, old_dir = local_studio_app(tmp_path)
    captured = {}

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "application/json"}
        content = b'{"choices":[{"message":{"content":"hello chat"}}],"usage":{"prompt_tokens":1,"completion_tokens":2}}'

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "hello chat"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 2}}

    class FakeClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, headers, json):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(routes_local_studio, "_new_http_client", FakeClient)
    try:
        response = request_app(
            app,
            "POST",
            "/api/local-studio/chat",
            json={
                "base_url": "http://compat.example/v1",
                "timeout": 7,
                "interface_mode": "openai",
                "model": "gpt-5.4-mini",
                "message": "hello",
                "options": {"stream": False},
            },
        )
    finally:
        settings.local_studio_dir = old_dir

    assert response.status_code == 200
    assert captured["timeout"] == 7
    assert captured["url"] == "http://compat.example/v1/chat/completions"
    assert captured["json"]["messages"][0]["content"][0]["text"] == "hello"
    assert response.json()["conversation"]["messages"][-1]["content"] == "hello chat"


def test_chat_route_image_tool_http_error_does_not_call_images_api(tmp_path, monkeypatch):
    app, old_dir = local_studio_app(tmp_path)
    captured = []

    class FakeClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, headers, json):
            captured.append((url, json))
            request = httpx.Request("POST", url)
            response = httpx.Response(502, request=request, text="tool unsupported")
            raise httpx.HTTPStatusError("bad gateway", request=request, response=response)

    monkeypatch.setattr(routes_local_studio, "_new_http_client", FakeClient)
    try:
        response = request_app(
            app,
            "POST",
            "/api/local-studio/chat",
            json={
                "base_url": "http://compat.example/v1",
                "model": "gpt-5.4-mini",
                "message": "make a smoke-test square",
                "options": {"image_tool_enabled": True, "size": "1536x864", "quality": "low", "background": "opaque", "output_format": "png"},
            },
        )
    finally:
        settings.local_studio_dir = old_dir

    assert response.status_code == 502
    assert [url for url, _ in captured] == ["http://compat.example/v1/responses"]
    assert response.json()["detail"]["message"] == "HTTP 502: tool unsupported"


def test_chat_route_image_tool_transport_error_does_not_call_images_api(tmp_path, monkeypatch):
    app, old_dir = local_studio_app(tmp_path)
    captured = []

    class FakeClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, headers, json):
            captured.append(url)
            raise httpx.ReadError("peer closed connection without sending complete message body")

    monkeypatch.setattr(routes_local_studio, "_new_http_client", FakeClient)
    try:
        response = request_app(
            app,
            "POST",
            "/api/local-studio/chat",
            json={
                "base_url": "http://compat.example/v1",
                "model": "gpt-5.4-mini",
                "message": "make a smoke-test circle",
                "options": {"image_tool_enabled": True, "size": "1536x864", "quality": "low"},
            },
        )
    finally:
        settings.local_studio_dir = old_dir

    assert response.status_code == 502
    assert captured == ["http://compat.example/v1/responses"]
    assert "peer closed connection" in response.json()["detail"]["message"]


def test_responses_stream_completed_event_extracts_image_candidates():
    parsed = parse_local_studio_stream_event(
        "responses",
        {
            "type": "response.completed",
            "response": {
                "output": [
                    {"type": "message", "content": [{"type": "output_text", "text": "done"}]},
                    {"type": "image_generation_call", "result": "ZmFrZQ=="},
                ],
                "usage": {"input_tokens": 1, "output_tokens": 2},
            },
        },
    )

    assert parsed["content"] == "done"
    assert parsed["usage"] == {"input_tokens": 1, "output_tokens": 2}
    assert parsed["image_candidates"] == [{"result": "ZmFrZQ==", "mime": "image/png"}]


def test_stream_chat_persists_response_image_candidates(tmp_path, monkeypatch):
    app, old_dir = local_studio_app(tmp_path)

    class FakeStreamResponse:
        status_code = 200
        headers = {"content-type": "text/event-stream"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            events = [
                {"type": "response.output_text.delta", "delta": "done"},
                {
                    "type": "response.completed",
                    "response": {
                        "output": [
                            {"type": "message", "content": [{"type": "output_text", "text": "done"}]},
                            {"type": "image_generation_call", "result": "ZmFrZQ=="},
                        ],
                        "usage": {"input_tokens": 1, "output_tokens": 2},
                    },
                },
            ]
            for event in events:
                yield "data: " + json.dumps(event)
                yield ""

    class FakeClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        def stream(self, method, url, headers, json):
            return FakeStreamResponse()

    monkeypatch.setattr(routes_local_studio, "_new_http_client", FakeClient)
    try:
        response = request_app(
            app,
            "POST",
            "/api/local-studio/chat",
            json={
                "base_url": "http://compat.example/v1",
                "model": "gpt-5.4-mini",
                "message": "make a cat image",
                "options": {"stream": True, "image_tool_enabled": True},
            },
        )
    finally:
        settings.local_studio_dir = old_dir

    assert response.status_code == 200
    completed = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ") and json.loads(line[6:]).get("type") == "local_studio.completed"
    ][0]
    assistant = completed["conversation"]["messages"][-1]
    assert assistant["content"] == "done"
    assert assistant["images"][0]["url"].startswith("/api/local-studio/assets/")


def test_stream_chat_image_tool_without_candidates_does_not_call_images_api(tmp_path, monkeypatch):
    app, old_dir = local_studio_app(tmp_path)
    captured_posts = []

    class FakeStreamResponse:
        status_code = 200
        headers = {"content-type": "text/event-stream"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            yield 'data: {"type":"response.completed","response":{"output":[],"usage":{"input_tokens":1,"output_tokens":1}}}'
            yield ""

    class FakeClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        def stream(self, method, url, headers, json):
            return FakeStreamResponse()

        async def post(self, url, headers, json):
            captured_posts.append((url, json))
            raise AssertionError("Local Studio Responses image tool must not call /images/generations")

    monkeypatch.setattr(routes_local_studio, "_new_http_client", FakeClient)
    try:
        response = request_app(
            app,
            "POST",
            "/api/local-studio/chat",
            json={
                "base_url": "http://compat.example/v1",
                "model": "gpt-5.4-mini",
                "message": "make a cat image",
                "options": {"stream": True, "image_tool_enabled": True, "size": "1536x864"},
            },
        )
    finally:
        settings.local_studio_dir = old_dir

    completed = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ") and json.loads(line[6:]).get("type") == "local_studio.completed"
    ][0]

    assert response.status_code == 200
    assert captured_posts == []
    assert completed["conversation"]["messages"][-1]["content"] == "(no response content)"
    assert completed["conversation"]["messages"][-1]["images"] == []


def test_chat_route_surfaces_http_524_and_records_error(tmp_path, monkeypatch):
    app, old_dir = local_studio_app(tmp_path)
    store = LocalStudioStore(tmp_path)
    conversation = store.create({"model": "gpt-5.4-mini"})

    class FakeClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, headers, json):
            request = httpx.Request("POST", url)
            response = httpx.Response(524, request=request, text="upstream timeout")
            raise httpx.HTTPStatusError("timeout", request=request, response=response)

    monkeypatch.setattr(routes_local_studio, "_new_http_client", FakeClient)
    try:
        response = request_app(
            app,
            "POST",
            "/api/local-studio/chat",
            json={
                "base_url": "http://compat.example/v1",
                "model": "gpt-5.4-mini",
                "conversation_id": conversation["id"],
                "message": "make a cat fishing image",
            },
        )
        saved = store.get(conversation["id"])
    finally:
        settings.local_studio_dir = old_dir

    assert response.status_code == 502
    assert "HTTP 524" in response.json()["detail"]["message"]
    assert "HTTP 524" in saved["messages"][-1]["error"]


def test_normalize_openai_base_url_rejects_non_http_url():
    try:
        normalize_openai_base_url("file:///tmp/api")
    except ValueError as exc:
        assert "http:// or https://" in str(exc)
    else:
        raise AssertionError("expected invalid base URL")
