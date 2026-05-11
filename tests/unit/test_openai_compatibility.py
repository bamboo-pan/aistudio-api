import asyncio
import json

import httpx

from aistudio_api.api.app import app
from aistudio_api.api.dependencies import get_client
from aistudio_api.api.state import runtime_state
from aistudio_api.domain.models import Candidate, ModelOutput


class FakeTextClient:
    def __init__(self, *, text: str = "ok", function_calls: list[dict] | None = None):
        self.text = text
        self.function_calls = function_calls or []
        self.calls = []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return ModelOutput(
            candidates=[Candidate(text=self.text, function_calls=self.function_calls)],
            usage={"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
        )


class FakeStreamClient:
    def __init__(self):
        self.calls = []

    async def stream_generate_content(self, **kwargs):
        self.calls.append(kwargs)
        yield ("tool_calls", [{"name": "lookup", "args": {"query": "weather"}}])
        yield ("usage", {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3})


def request_with_client(client, method: str, url: str, **kwargs) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http_client:
            return await http_client.request(method, url, **kwargs)

    old_busy_lock = runtime_state.busy_lock
    old_account_service = runtime_state.account_service
    old_rotator = runtime_state.rotator
    app.dependency_overrides[get_client] = lambda: client
    runtime_state.busy_lock = asyncio.Semaphore(3)
    runtime_state.account_service = None
    runtime_state.rotator = None
    try:
        return asyncio.run(send())
    finally:
        runtime_state.busy_lock = old_busy_lock
        runtime_state.account_service = old_account_service
        runtime_state.rotator = old_rotator
        app.dependency_overrides.pop(get_client, None)


def test_openai_responses_accepts_text_format_json_schema():
    client = FakeTextClient(text='{"ok":true}')

    response = request_with_client(
        client,
        "POST",
        "/v1/responses",
        json={
            "model": "gemini-3-flash-preview",
            "input": "return json",
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "Answer",
                    "strict": True,
                    "schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}},
                }
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "response"
    assert body["output_text"] == '{"ok":true}'
    assert body["output"][0]["content"][0]["type"] == "output_text"
    call = client.calls[0]
    assert call["generation_config_overrides"]["response_mime_type"] == "application/json"
    assert call["generation_config_overrides"]["response_schema"] == [6, None, None, None, None, None, [["ok", [4]]]]
    assert call["sanitize_plain_text"] is False


def test_openai_responses_maps_function_calls_to_output_items():
    client = FakeTextClient(text="", function_calls=[{"name": "lookup", "args": {"query": "weather"}}])

    response = request_with_client(
        client,
        "POST",
        "/v1/responses",
        json={"model": "gemini-3-flash-preview", "input": "call a tool"},
    )

    assert response.status_code == 200
    function_call = response.json()["output"][0]
    assert function_call["type"] == "function_call"
    assert function_call["name"] == "lookup"
    assert json.loads(function_call["arguments"]) == {"query": "weather"}


def test_openai_responses_forwards_thinking_control():
    client = FakeTextClient(text="ok")

    response = request_with_client(
        client,
        "POST",
        "/v1/responses",
        json={"model": "gemini-3-flash-preview", "input": "hello", "thinking": "off"},
    )

    assert response.status_code == 200
    assert client.calls[0]["enable_thinking"] is False


def test_openai_responses_accepts_flat_function_tool_input():
    client = FakeTextClient(text="ok")

    response = request_with_client(
        client,
        "POST",
        "/v1/responses",
        json={
            "model": "gemini-3-flash-preview",
            "input": "use a tool if needed",
            "tools": [
                {
                    "type": "function",
                    "name": "lookup",
                    "description": "look things up",
                    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
                }
            ],
        },
    )

    assert response.status_code == 200
    assert client.calls[0]["tools"] is not None


def test_messages_accepts_anthropic_tools_and_returns_tool_use_blocks():
    client = FakeTextClient(text="", function_calls=[{"name": "lookup", "args": {"query": "weather"}}])

    response = request_with_client(
        client,
        "POST",
        "/v1/messages",
        json={
            "model": "gemini-3-flash-preview",
            "system": "be terse",
            "messages": [{"role": "user", "content": [{"type": "text", "text": "use the tool"}]}],
            "tools": [
                {
                    "name": "lookup",
                    "description": "look things up",
                    "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "message"
    assert body["stop_reason"] == "tool_use"
    assert body["content"][0] == {"type": "tool_use", "id": body["content"][0]["id"], "name": "lookup", "input": {"query": "weather"}}
    assert client.calls[0]["tools"] is not None


def test_chat_streaming_tool_calls_include_openai_delta_index_and_string_arguments():
    client = FakeStreamClient()

    response = request_with_client(
        client,
        "POST",
        "/v1/chat/completions",
        json={
            "model": "gemini-3-flash-preview",
            "stream": True,
            "messages": [{"role": "user", "content": "call a tool"}],
            "tools": [{"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}],
        },
    )

    assert response.status_code == 200
    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ") and line != "data: [DONE]"
    ]
    tool_event = next(event for event in events if event.get("choices") and event["choices"][0]["delta"].get("tool_calls"))
    tool_call = tool_event["choices"][0]["delta"]["tool_calls"][0]
    assert tool_call["index"] == 0
    assert tool_call["type"] == "function"
    assert tool_call["function"]["name"] == "lookup"
    assert json.loads(tool_call["function"]["arguments"]) == {"query": "weather"}
    assert any(event.get("choices") and event["choices"][0]["finish_reason"] == "tool_calls" for event in events)


def test_openai_routes_return_standard_error_shape():
    response = request_with_client(FakeTextClient(), "POST", "/v1/responses", json={"input": "hello"})

    assert response.status_code == 400
    body = response.json()
    assert "detail" not in body
    assert body["error"] == {
        "message": "model is required",
        "type": "invalid_request_error",
        "param": None,
        "code": None,
    }