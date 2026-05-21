import asyncio

import httpx
from fastapi import FastAPI

from aistudio_api.api import routes_local_studio
from aistudio_api.api.routes_local_studio import router as local_studio_router
from aistudio_api.config import settings
from aistudio_api.infrastructure.local_studio import (
    GPT_IMAGE_2_SIZE_OPTIONS,
    LocalStudioStore,
    build_images_generation_payload,
    build_responses_payload,
    filter_chat_models,
    normalize_openai_base_url,
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


def test_local_studio_conversation_routes_round_trip_and_bulk_delete(tmp_path):
    app, old_dir = local_studio_app(tmp_path)
    try:
        created = request_app(app, "POST", "/api/local-studio/conversations", json={"title": "Draft", "model": "gpt-5.4-mini"})
        assert created.status_code == 200
        conversation = created.json()

        patched = request_app(app, "PATCH", f"/api/local-studio/conversations/{conversation['id']}", json={"title": "Renamed"})
        listed = request_app(app, "GET", "/api/local-studio/conversations")
        fetched = request_app(app, "GET", f"/api/local-studio/conversations/{conversation['id']}")
        deleted = request_app(app, "POST", "/api/local-studio/conversations/bulk-delete", json={"ids": [conversation["id"], "missing"]})
        missing = request_app(app, "GET", f"/api/local-studio/conversations/{conversation['id']}")

        assert patched.json()["title"] == "Renamed"
        assert listed.json()["data"][0]["title"] == "Renamed"
        assert fetched.json()["model"] == "gpt-5.4-mini"
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


def test_build_images_generation_payload_uses_validated_gpt_image_2_options():
    payload = build_images_generation_payload(
        "make a smoke-test square",
        {"size": "1536x864", "quality": "low", "background": "opaque", "output_format": "png", "output_compression": 90},
    )

    assert payload == {
        "model": "gpt-image-2",
        "prompt": "make a smoke-test square",
        "n": 1,
        "size": "1536x864",
        "quality": "low",
        "background": "opaque",
        "output_format": "png",
        "output_compression": 90,
    }


def test_chat_route_posts_responses_payload_and_persists_reply(tmp_path, monkeypatch):
    app, old_dir = local_studio_app(tmp_path)
    captured = {}

    class FakeResponse:
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


def test_chat_route_falls_back_to_images_api_for_image_tool(tmp_path, monkeypatch):
    app, old_dir = local_studio_app(tmp_path)
    captured = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class FakeClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, headers, json):
            captured.append((url, json))
            if url.endswith("/responses"):
                request = httpx.Request("POST", url)
                response = httpx.Response(502, request=request, text="tool unsupported")
                raise httpx.HTTPStatusError("bad gateway", request=request, response=response)
            return FakeResponse({"created": 1, "data": [{"b64_json": "ZmFrZQ=="}]})

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

    body = response.json()
    assert response.status_code == 200
    assert [url for url, _ in captured] == ["http://compat.example/v1/responses", "http://compat.example/v1/images/generations"]
    assert captured[1][1]["model"] == "gpt-image-2"
    assert captured[1][1]["size"] == "1536x864"
    assert body["conversation"]["messages"][-1]["content"] == "Generated image"
    assert body["conversation"]["messages"][-1]["images"][0]["url"].startswith("/api/local-studio/assets/")


def test_chat_route_falls_back_to_images_api_for_responses_transport_error(tmp_path, monkeypatch):
    app, old_dir = local_studio_app(tmp_path)
    captured = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"b64_json": "ZmFrZQ=="}]}

    class FakeClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, headers, json):
            captured.append(url)
            if url.endswith("/responses"):
                raise httpx.ReadError("peer closed connection without sending complete message body")
            return FakeResponse()

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

    assert response.status_code == 200
    assert captured == ["http://compat.example/v1/responses", "http://compat.example/v1/images/generations"]
    assert response.json()["conversation"]["messages"][-1]["images"]


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
