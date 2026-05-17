import asyncio
import json

from aistudio_api.infrastructure.cache.snapshot_cache import SnapshotCache
from aistudio_api.infrastructure.gateway.client import AIStudioClient
from aistudio_api.infrastructure.gateway.capture import RequestCaptureService


class FakeBrowserSession:
    def __init__(self):
        self.template_calls = []

    async def capture_template(self, model):
        self.template_calls.append(model)
        call_number = len(self.template_calls)
        template_body = json.dumps(
            [
                "models/gemini-3-flash-preview",
                [[[[None, "template"]], "user"]],
                None,
                [],
                "template-snapshot",
            ]
        )
        return {
            "url": "https://example.test/GenerateContent",
            "headers": {"content-type": "application/json+protobuf", "x-template-call": str(call_number)},
            "body": template_body,
        }

    async def generate_snapshot(self, contents):
        return "fresh-snapshot"


def test_capture_rewrites_template_with_requested_model():
    service = RequestCaptureService(FakeBrowserSession(), SnapshotCache(ttl=60, max_size=10))

    captured = asyncio.run(service.capture("draw a large image", model="gemini-3.1-flash-image-preview"))

    assert captured is not None
    assert captured.model == "models/gemini-3.1-flash-image-preview"
    body = json.loads(captured.body)
    assert body[0] == "models/gemini-3.1-flash-image-preview"
    assert body[4] == "fresh-snapshot"


def test_capture_template_cache_can_be_cleared():
    session = FakeBrowserSession()
    service = RequestCaptureService(session, SnapshotCache(ttl=60, max_size=10))

    first = asyncio.run(service.capture("first prompt", model="gemini-3.1-flash-lite"))
    second = asyncio.run(service.capture("second prompt", model="gemini-3.1-flash-lite"))

    assert first.headers["x-template-call"] == "1"
    assert second.headers["x-template-call"] == "1"
    assert session.template_calls == ["gemini-3.1-flash-lite"]

    service.clear_templates()
    third = asyncio.run(service.capture("third prompt", model="gemini-3.1-flash-lite"))

    assert third.headers["x-template-call"] == "2"
    assert session.template_calls == ["gemini-3.1-flash-lite", "gemini-3.1-flash-lite"]


def test_client_switch_auth_clears_capture_templates(tmp_path):
    auth_file = tmp_path / "auth.json"
    auth_file.write_text("{}")
    client = AIStudioClient()
    try:
        client._capture_service._templates["gemini-3.1-flash-lite"] = object()

        asyncio.run(client.switch_auth(str(auth_file)))

        assert client._capture_service._templates == {}
    finally:
        if client._session is not None:
            client._session._executor.shutdown(wait=False)
