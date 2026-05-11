import asyncio
import base64
import json

import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from aistudio_api.api.schemas import ChatRequest, ImageRequest
from aistudio_api.api.state import runtime_state
from aistudio_api.application.api_service import handle_chat, handle_image_generation
from aistudio_api.domain.models import Candidate, GeneratedImage, ModelOutput


class FakeImageClient:
    def __init__(self):
        self.calls = []

    async def generate_image(self, *, prompt, model, generation_config_overrides=None):
        self.calls.append(
            {
                "prompt": prompt,
                "model": model,
                "generation_config_overrides": generation_config_overrides,
            }
        )
        image_bytes = f"image-{len(self.calls)}".encode("ascii")
        return ModelOutput(
            candidates=[
                Candidate(
                    text=f"revised-{len(self.calls)}",
                    images=[GeneratedImage(mime="image/png", data=image_bytes, size=len(image_bytes))],
                )
            ],
            usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        )


def run_with_runtime(coro):
    old_busy_lock = runtime_state.busy_lock
    old_account_service = runtime_state.account_service
    old_rotator = runtime_state.rotator
    runtime_state.busy_lock = asyncio.Semaphore(3)
    runtime_state.account_service = None
    runtime_state.rotator = None
    try:
        return asyncio.run(coro)
    finally:
        runtime_state.busy_lock = old_busy_lock
        runtime_state.account_service = old_account_service
        runtime_state.rotator = old_rotator


def run_stream_with_runtime(coro):
    async def collect():
        response = await coro
        assert isinstance(response, StreamingResponse)
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk)
        return response, "".join(chunks)

    return run_with_runtime(collect())


def test_image_generation_runs_n_sequential_calls_and_aggregates_images():
    client = FakeImageClient()
    req = ImageRequest(
        prompt="draw a city",
        model="gemini-3.1-flash-image-preview",
        n=2,
        size="1024x1024",
    )

    response = run_with_runtime(handle_image_generation(req, client))

    assert len(client.calls) == 2
    assert all(call["model"] == "gemini-3.1-flash-image-preview" for call in client.calls)
    assert all(call["generation_config_overrides"] == {"output_image_size": [None, "1K"]} for call in client.calls)
    assert [base64.b64decode(item["b64_json"]) for item in response["data"]] == [b"image-1", b"image-2"]


def test_image_generation_rejects_unsupported_size_before_client_call():
    client = FakeImageClient()
    req = ImageRequest(prompt="draw", model="gemini-3.1-flash-image-preview", size="256x256")

    with pytest.raises(HTTPException) as error:
        run_with_runtime(handle_image_generation(req, client))

    assert error.value.status_code == 400
    assert "256x256" in error.value.detail["message"]
    assert client.calls == []


def test_image_generation_accepts_url_response_format_with_data_url_fallback():
    client = FakeImageClient()
    req = ImageRequest(prompt="draw", model="gemini-3.1-flash-image-preview", response_format="url")

    response = run_with_runtime(handle_image_generation(req, client))

    assert len(client.calls) == 1
    item = response["data"][0]
    assert item["url"] == "data:image/png;base64,aW1hZ2UtMQ=="
    assert base64.b64decode(item["b64_json"]) == b"image-1"


def test_image_generation_rejects_unknown_response_format_before_client_call():
    client = FakeImageClient()
    req = ImageRequest(prompt="draw", model="gemini-3.1-flash-image-preview", response_format="file")

    with pytest.raises(HTTPException) as error:
        run_with_runtime(handle_image_generation(req, client))

    assert error.value.status_code == 400
    assert "response_format" in error.value.detail["message"]
    assert client.calls == []


def test_chat_completion_with_image_model_returns_markdown_image():
    client = FakeImageClient()
    req = ChatRequest(
        model="gemini-3.1-flash-image-preview",
        messages=[{"role": "user", "content": "draw a city"}],
    )

    response = run_with_runtime(handle_chat(req, client))

    assert len(client.calls) == 1
    assert client.calls[0]["prompt"] == "draw a city"
    content = response["choices"][0]["message"]["content"]
    assert content == "![generated image 1](data:image/png;base64,aW1hZ2UtMQ==)"


def test_chat_completion_with_image_model_ignores_stream_true_and_returns_sse_image():
    client = FakeImageClient()
    req = ChatRequest(
        model="gemini-3.1-flash-image-preview",
        messages=[{"role": "user", "content": "draw a city"}],
        stream=True,
    )

    response, stream = run_stream_with_runtime(handle_chat(req, client))

    assert response.media_type == "text/event-stream"
    assert len(client.calls) == 1
    assert "streaming responses" not in stream
    payload = json.loads(stream.split("\n\n", 1)[0].removeprefix("data: "))
    assert payload["choices"][0]["delta"]["content"] == "![generated image 1](data:image/png;base64,aW1hZ2UtMQ==)"
    assert "data: [DONE]" in stream