import asyncio
import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aistudio_api.api.dependencies import get_runtime_state
from aistudio_api.api.routes_request_logs import router as request_logs_router
from aistudio_api.infrastructure.gateway.capture import CapturedRequest
from aistudio_api.infrastructure.gateway.replay import RequestReplayService
from aistudio_api.infrastructure.gateway.streaming import StreamingGateway
from aistudio_api.infrastructure.request_logs import RequestLogStore


def _captured_request() -> CapturedRequest:
    body = json.dumps(
        [
            "models/gemini-3.1-flash-lite",
            [[[[None, "template"]], "user"]],
            None,
            [],
            "template-snapshot",
        ]
    )
    return CapturedRequest(
        url="https://aistudio.google.com/_/BardChatUi/data/batchexecute/GenerateContent",
        headers={
            "host": "aistudio.google.com",
            "content-length": "999",
            "content-type": "application/json+protobuf",
            "cookie": "SID=secret",
        },
        body=body,
    )


class FakeReplaySession:
    async def send_hooked_request(self, *, body, url, headers, timeout_ms):
        return 200, b"ok"


class FakeStreamingSession:
    async def send_streaming_request(self, *, body, url, headers, timeout_ms):
        yield "status", 200


def test_request_log_store_persists_toggle_and_complete_request(tmp_path):
    store = RequestLogStore(tmp_path)

    assert store.status() == {"enabled": False, "count": 0}
    assert store.save(kind="generate_content", model="m", method="POST", url="u", headers={}, body="{}") is None

    status = store.set_enabled(True)
    assert status["enabled"] is True
    entry = store.save(
        kind="generate_content",
        model="gemini-test",
        method="POST",
        url="https://aistudio.google.com/rpc",
        headers={"content-type": "application/json", "x-test": 3},
        captured_headers={"host": "aistudio.google.com", "content-length": "12", "x-test": 3},
        body='{"hello":[1,true]}',
        transport="browser",
    )

    assert entry is not None
    assert store.count() == 1
    summary = store.list()[0]
    assert summary["id"] == entry["id"]
    assert summary["body_size"] == len('{"hello":[1,true]}'.encode())

    detail = store.get(entry["id"])
    assert detail["headers"] == {"content-type": "application/json", "x-test": "3"}
    assert detail["captured_headers"]["host"] == "aistudio.google.com"
    assert detail["body_raw"] == '{"hello":[1,true]}'
    assert detail["body_json"] == {"hello": [1, True]}
    assert detail["body_parse_error"] is None


def test_request_log_routes_manage_status_list_and_detail(tmp_path):
    store = RequestLogStore(tmp_path)
    runtime_state = SimpleNamespace(request_log_store=store)
    app = FastAPI()
    app.include_router(request_logs_router)
    app.dependency_overrides[get_runtime_state] = lambda: runtime_state
    client = TestClient(app)

    assert client.get("/request-logs/status").json() == {"enabled": False, "count": 0}
    assert client.put("/request-logs/status", json={"enabled": True}).json()["enabled"] is True
    saved = store.save(kind="generate_image", model="image-model", method="POST", url="https://aistudio.google.com/rpc", headers={}, body="[]")

    listing = client.get("/request-logs").json()
    assert listing["enabled"] is True
    assert listing["total"] == 1
    assert listing["data"][0]["id"] == saved["id"]

    detail = client.get(f"/request-logs/{saved['id']}").json()
    assert detail["kind"] == "generate_image"
    assert detail["body_raw"] == "[]"
    assert client.get("/request-logs/not-a-valid-id").status_code == 400


def test_replay_logs_actual_outbound_request_when_enabled(tmp_path):
    store = RequestLogStore(tmp_path)
    store.set_enabled(True)
    captured = _captured_request()
    replay = RequestReplayService(session=FakeReplaySession(), request_log_store=store)

    status, raw = asyncio.run(replay.replay(captured, body='{"rewritten":true}', kind="generate_content", model="gemini-test"))

    assert status == 200
    assert raw == b"ok"
    detail = store.get(store.list()[0]["id"])
    assert detail["kind"] == "generate_content"
    assert detail["model"] == "gemini-test"
    assert detail["transport"] == "browser"
    assert detail["headers"] == {"content-type": "application/json+protobuf", "cookie": "SID=secret"}
    assert detail["captured_headers"]["content-length"] == "999"
    assert detail["body_json"] == {"rewritten": True}


def test_replay_does_not_log_when_disabled(tmp_path):
    store = RequestLogStore(tmp_path)
    replay = RequestReplayService(session=FakeReplaySession(), request_log_store=store)

    asyncio.run(replay.replay(_captured_request(), body='{"rewritten":true}', kind="generate_content", model="gemini-test"))

    assert store.count() == 0


def test_streaming_logs_actual_outbound_request_when_enabled(tmp_path):
    store = RequestLogStore(tmp_path)
    store.set_enabled(True)
    gateway = StreamingGateway(session=FakeStreamingSession(), request_log_store=store)

    events = asyncio.run(
        _collect_stream_events(
            gateway.stream_chat(
                captured=_captured_request(),
                model="gemini-stream",
                system_instruction=None,
            )
        )
    )

    assert events == [("usage", None), ("done", None)]
    detail = store.get(store.list()[0]["id"])
    assert detail["kind"] == "stream_generate_content"
    assert detail["model"] == "gemini-stream"
    assert detail["transport"] == "browser_stream"
    assert json.loads(detail["body_raw"])[0] == "models/gemini-stream"


async def _collect_stream_events(stream):
    events = []
    async for event in stream:
        events.append(event)
    return events