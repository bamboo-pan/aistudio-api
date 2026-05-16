import asyncio
import json

from aistudio_api.infrastructure.cache.snapshot_cache import SnapshotCache
from aistudio_api.infrastructure.gateway.capture import RequestCaptureService


class FakeBrowserSession:
    async def capture_template(self, model):
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
            "headers": {"content-type": "application/json+protobuf"},
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