import asyncio
import json

import httpx
import pytest

from aistudio_api.api.app import app
from aistudio_api.api.dependencies import get_client
from aistudio_api.api.state import runtime_state
from aistudio_api.domain.model_capabilities import clear_dynamic_model_capabilities, get_model_capabilities
from aistudio_api.domain.models import Candidate, ModelOutput


class FakeTextClient:
    def __init__(self, *, text: str = "ok", thinking: str = "", function_calls: list[dict] | None = None):
        self.text = text
        self.thinking = thinking
        self.function_calls = function_calls or []
        self.calls = []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return ModelOutput(
            candidates=[Candidate(text=self.text, thinking=self.thinking, function_calls=self.function_calls)],
            usage={"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
        )


class FakeStreamClient:
    def __init__(self, events: list[tuple[str, object]] | None = None):
        self.calls = []
        self.events = events or [
            ("tool_calls", [{"name": "lookup", "args": {"query": "weather"}}]),
            ("usage", {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}),
        ]

    async def stream_generate_content(self, **kwargs):
        self.calls.append(kwargs)
        for event in self.events:
            yield event


class ModelListClient(FakeTextClient):
    def __init__(self, models: list[str]):
        super().__init__()
        self.models = models
        self.list_calls = 0

    async def list_available_models(self):
        self.list_calls += 1
        return self.models


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


def test_openai_models_refresh_registers_discovered_models():
    client = ModelListClient(["models/gemini-dynamic-preview"])
    old_client = runtime_state.client
    runtime_state.client = client
    clear_dynamic_model_capabilities()
    try:
        response = request_with_client(FakeTextClient(), "GET", "/v1/models?refresh=true")
        capabilities = get_model_capabilities("gemini-dynamic-preview", strict=True)
    finally:
        runtime_state.client = old_client
        clear_dynamic_model_capabilities()

    assert response.status_code == 200
    assert client.list_calls == 1
    assert capabilities.text_output is True
    assert any(model["id"] == "gemini-dynamic-preview" for model in response.json()["data"])


def test_openai_responses_accepts_output_text_history_blocks():
    client = FakeTextClient(text="fresh answer")

    response = request_with_client(
        client,
        "POST",
        "/v1/responses",
        json={
            "model": "gemini-3-flash-preview",
            "input": [
                {"role": "user", "content": "nihao"},
                {
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "你好！有什么我可以帮你的吗？"}],
                },
                {"role": "user", "content": "看下今日头条新闻"},
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["output_text"] == "fresh answer"
    contents = client.calls[0]["contents"]
    assert contents[1].role == "model"
    assert contents[1].parts[0].text == "你好！有什么我可以帮你的吗？"


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


def test_openai_responses_forwards_enabled_thinking_level():
    client = FakeTextClient(text="ok")

    response = request_with_client(
        client,
        "POST",
        "/v1/responses",
        json={"model": "gemini-3-flash-preview", "input": "hello", "thinking": "high"},
    )

    assert response.status_code == 200
    call = client.calls[0]
    assert call["enable_thinking"] is True
    assert call["generation_config_overrides"]["thinking_config"] == [1, None, None, 3]
    assert call["generation_config_overrides"]["request_flag"] == 1


def test_openai_responses_returns_thinking_output():
    client = FakeTextClient(text="answer", thinking="private reasoning")

    response = request_with_client(
        client,
        "POST",
        "/v1/responses",
        json={"model": "gemini-3-flash-preview", "input": "hello", "thinking": "high"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["thinking"] == "private reasoning"
    reasoning = body["output"][0]
    assert reasoning["type"] == "reasoning"
    assert reasoning["content"][0] == {"type": "reasoning_text", "text": "private reasoning"}
    assert body["output"][1]["content"][0]["text"] == "answer"


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


@pytest.mark.parametrize("tool_type", ["web_search", "web_search_preview", "browser_search"])
def test_chat_completions_accepts_search_tool_shapes(tool_type):
    client = FakeTextClient(text="grounded")

    response = request_with_client(
        client,
        "POST",
        "/v1/chat/completions",
        json={
            "model": "gemini-3-flash-preview",
            "messages": [{"role": "user", "content": "search the web"}],
            "tools": [{"type": tool_type}],
        },
    )

    assert response.status_code == 200
    assert client.calls[0]["tools"] == [[None, None, None, [None, [[]]]]]


def test_openai_responses_accepts_web_search_tool_and_outputs_search_call():
    client = FakeTextClient(text="grounded")

    response = request_with_client(
        client,
        "POST",
        "/v1/responses",
        json={"model": "gemini-3-flash-preview", "input": "search", "tools": [{"type": "web_search"}]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["output"][0]["type"] == "web_search_call"
    assert body["output"][1]["content"][0]["text"] == "grounded"
    assert client.calls[0]["tools"] == [[None, None, None, [None, [[]]]]]


def test_openai_responses_streaming_emits_responses_events():
    client = FakeStreamClient(events=[("body", "hello"), ("usage", {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3})])

    response = request_with_client(
        client,
        "POST",
        "/v1/responses",
        json={"model": "gemini-3-flash-preview", "input": "hello", "stream": True},
    )

    assert response.status_code == 200
    assert "event: response.created" in response.text
    assert "event: response.output_text.delta" in response.text
    assert '"delta": "hello"' in response.text
    assert "event: response.completed" in response.text


def test_openai_responses_streaming_emits_reasoning_events():
    client = FakeStreamClient(events=[("thinking", "plan"), ("body", "answer"), ("usage", {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3})])

    response = request_with_client(
        client,
        "POST",
        "/v1/responses",
        json={"model": "gemini-3-flash-preview", "input": "hello", "thinking": "high", "stream": True},
    )

    assert response.status_code == 200
    assert "event: response.reasoning.delta" in response.text
    assert '"delta": "plan"' in response.text
    assert "event: response.reasoning.done" in response.text
    assert '"thinking": "plan"' in response.text


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


def test_messages_accepts_anthropic_web_search_tool():
    client = FakeTextClient(text="grounded")

    response = request_with_client(
        client,
        "POST",
        "/v1/messages",
        json={
            "model": "gemini-3-flash-preview",
            "messages": [{"role": "user", "content": "search"}],
            "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
        },
    )

    assert response.status_code == 200
    assert client.calls[0]["tools"] == [[None, None, None, [None, [[]]]]]


def test_messages_streaming_emits_anthropic_text_events():
    client = FakeStreamClient(events=[("body", "hello"), ("usage", {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3})])

    response = request_with_client(
        client,
        "POST",
        "/v1/messages",
        json={"model": "gemini-3-flash-preview", "stream": True, "messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 200
    assert "event: message_start" in response.text
    assert "event: content_block_delta" in response.text
    assert '"text": "hello"' in response.text
    assert "event: message_stop" in response.text


def test_messages_streaming_emits_tool_use_events():
    client = FakeStreamClient()

    response = request_with_client(
        client,
        "POST",
        "/v1/messages",
        json={
            "model": "gemini-3-flash-preview",
            "stream": True,
            "messages": [{"role": "user", "content": "use tool"}],
            "tools": [{"name": "lookup", "input_schema": {"type": "object"}}],
        },
    )

    assert response.status_code == 200
    assert '"type": "tool_use"' in response.text
    assert '"type": "input_json_delta"' in response.text
    assert "event: message_stop" in response.text


def test_messages_count_tokens_returns_anthropic_shape():
    response = request_with_client(
        FakeTextClient(),
        "POST",
        "/v1/messages/count_tokens",
        json={
            "model": "gemini-3-flash-preview",
            "system": "be terse",
            "messages": [{"role": "user", "content": "hello world"}],
            "tools": [{"name": "lookup", "input_schema": {"type": "object"}}],
        },
    )

    assert response.status_code == 200
    assert response.json()["input_tokens"] >= 3


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