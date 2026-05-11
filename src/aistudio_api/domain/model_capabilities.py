"""Model capability registry used by API validation and UI metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


MODEL_CREATED = 1700000000
IMAGE_RESPONSE_FORMATS = ("b64_json", "url")


@dataclass(frozen=True)
class ImageSizeCapability:
    """Mapping from OpenAI-compatible image size to AI Studio request hints."""

    size: str
    aspect_ratio: str
    output_image_size: str | None = None
    prompt_suffix: str | None = None

    def generation_config_overrides(self) -> dict[str, Any]:
        if self.output_image_size is None:
            return {}
        return {"output_image_size": [None, self.output_image_size]}

    def to_public_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"size": self.size, "aspect_ratio": self.aspect_ratio}
        if self.output_image_size is not None:
            data["output_image_size"] = self.output_image_size
        return data


@dataclass(frozen=True)
class ModelCapabilities:
    id: str
    text_output: bool = True
    image_input: bool = False
    image_output: bool = False
    search: bool = False
    tools: bool = False
    thinking: bool = False
    streaming: bool = True
    owned_by: str = "google"
    unsupported_generation_fields: tuple[str, ...] = ()
    image_sizes: dict[str, ImageSizeCapability] = field(default_factory=dict)

    def to_model_dict(self) -> dict[str, Any]:
        capabilities = {
            "text_output": self.text_output,
            "image_input": self.image_input,
            "image_output": self.image_output,
            "search": self.search,
            "tools": self.tools,
            "thinking": self.thinking,
            "streaming": self.streaming,
        }
        data: dict[str, Any] = {
            "id": self.id,
            "object": "model",
            "created": MODEL_CREATED,
            "owned_by": self.owned_by,
            "capabilities": capabilities,
        }
        if self.image_sizes:
            data["image_generation"] = {
                "sizes": [size.to_public_dict() for size in self.image_sizes.values()],
                "response_formats": list(IMAGE_RESPONSE_FORMATS),
            }
        if self.unsupported_generation_fields:
            data["unsupported_generation_fields"] = list(self.unsupported_generation_fields)
        return data


IMAGE_MODEL_UNSUPPORTED_FIELDS = (
    "stop_sequences",
    "response_mime_type",
    "response_schema",
    "presence_penalty",
    "frequency_penalty",
    "response_logprobs",
    "logprobs",
    "media_resolution",
    "thinking_config",
    "request_flag",
)


DEFAULT_IMAGE_SIZES = {
    "512x512": ImageSizeCapability("512x512", aspect_ratio="1:1", output_image_size="512"),
    "1024x1024": ImageSizeCapability("1024x1024", aspect_ratio="1:1", output_image_size="1K"),
    "1024x1792": ImageSizeCapability(
        "1024x1792",
        aspect_ratio="9:16",
        output_image_size="1K",
        prompt_suffix="Use a vertical 9:16 composition.",
    ),
    "1792x1024": ImageSizeCapability(
        "1792x1024",
        aspect_ratio="16:9",
        output_image_size="1K",
        prompt_suffix="Use a horizontal 16:9 composition.",
    ),
}


def _text_model(
    model_id: str,
    *,
    image_input: bool = True,
    search: bool = True,
    tools: bool = True,
    thinking: bool = True,
    streaming: bool = True,
) -> ModelCapabilities:
    return ModelCapabilities(
        id=model_id,
        text_output=True,
        image_input=image_input,
        image_output=False,
        search=search,
        tools=tools,
        thinking=thinking,
        streaming=streaming,
    )


def _image_model(model_id: str) -> ModelCapabilities:
    return ModelCapabilities(
        id=model_id,
        text_output=True,
        image_input=True,
        image_output=True,
        search=False,
        tools=False,
        thinking=False,
        streaming=False,
        unsupported_generation_fields=IMAGE_MODEL_UNSUPPORTED_FIELDS,
        image_sizes=DEFAULT_IMAGE_SIZES,
    )


MODEL_CAPABILITIES: dict[str, ModelCapabilities] = {
    # Gemma 4 series
    "gemma-4-31b-it": _text_model("gemma-4-31b-it", image_input=False),
    "gemma-4-26b-a4b-it": _text_model("gemma-4-26b-a4b-it", image_input=False),
    # Gemini 3 series
    "gemini-3-flash-preview": _text_model("gemini-3-flash-preview"),
    "gemini-3.1-pro-preview": _text_model("gemini-3.1-pro-preview"),
    "gemini-3.1-flash-lite": _text_model("gemini-3.1-flash-lite"),
    "gemini-3.1-flash-image-preview": _image_model("gemini-3.1-flash-image-preview"),
    "gemini-3-pro-image-preview": _image_model("gemini-3-pro-image-preview"),
    "gemini-3.1-flash-live-preview": _text_model("gemini-3.1-flash-live-preview", tools=False, streaming=True),
    "gemini-3.1-flash-tts-preview": _text_model("gemini-3.1-flash-tts-preview", image_input=False, search=False, tools=False, thinking=False),
    # Latest aliases
    "gemini-pro-latest": _text_model("gemini-pro-latest"),
    "gemini-flash-latest": _text_model("gemini-flash-latest"),
    "gemini-flash-lite-latest": _text_model("gemini-flash-lite-latest"),
}


GENERIC_TEXT_CAPABILITIES = ModelCapabilities(
    id="unknown",
    text_output=True,
    image_input=True,
    image_output=False,
    search=True,
    tools=True,
    thinking=True,
    streaming=True,
)

GENERIC_IMAGE_CAPABILITIES = ModelCapabilities(
    id="unknown-image",
    text_output=True,
    image_input=True,
    image_output=True,
    search=False,
    tools=False,
    thinking=False,
    streaming=False,
    unsupported_generation_fields=IMAGE_MODEL_UNSUPPORTED_FIELDS,
    image_sizes=DEFAULT_IMAGE_SIZES,
)


def canonical_model_id(model: str) -> str:
    return model.removeprefix("models/")


def get_model_capabilities(model: str, *, strict: bool = False) -> ModelCapabilities:
    model_id = canonical_model_id(model)
    capabilities = MODEL_CAPABILITIES.get(model_id)
    if capabilities is not None:
        return capabilities
    if strict:
        raise ValueError(f"Model '{model}' is not registered")
    generic = GENERIC_IMAGE_CAPABILITIES if "image" in model_id.lower() else GENERIC_TEXT_CAPABILITIES
    return ModelCapabilities(
        id=model_id,
        text_output=generic.text_output,
        image_input=generic.image_input,
        image_output=generic.image_output,
        search=generic.search,
        tools=generic.tools,
        thinking=generic.thinking,
        streaming=generic.streaming,
        unsupported_generation_fields=generic.unsupported_generation_fields,
        image_sizes=generic.image_sizes,
    )


def list_model_metadata() -> list[dict[str, Any]]:
    return [capabilities.to_model_dict() for capabilities in MODEL_CAPABILITIES.values()]


def get_model_metadata(model: str) -> dict[str, Any]:
    return get_model_capabilities(model, strict=True).to_model_dict()


def require_model_capabilities(model: str) -> ModelCapabilities:
    return get_model_capabilities(model, strict=True)


@dataclass(frozen=True)
class ImageGenerationPlan:
    model: str
    size: str
    prompt_suffix: str | None
    generation_config_overrides: dict[str, Any]

    def prompt_for(self, prompt: str) -> str:
        if not self.prompt_suffix:
            return prompt
        return f"{prompt}\n\n{self.prompt_suffix}"


def plan_image_generation(model: str, size: str) -> ImageGenerationPlan:
    capabilities = require_model_capabilities(model)
    if not capabilities.image_output:
        raise ValueError(f"Model '{model}' does not support image generation")
    size_capability = capabilities.image_sizes.get(size)
    if size_capability is None:
        supported = ", ".join(capabilities.image_sizes) or "none"
        raise ValueError(f"Model '{model}' does not support image size '{size}'. Supported sizes: {supported}")
    overrides = size_capability.generation_config_overrides()
    return ImageGenerationPlan(
        model=capabilities.id,
        size=size,
        prompt_suffix=size_capability.prompt_suffix,
        generation_config_overrides=overrides,
    )


def validate_chat_capabilities(
    model: str,
    *,
    has_image_input: bool,
    uses_tools: bool,
    uses_search: bool,
    uses_thinking: bool,
    stream: bool,
) -> ModelCapabilities:
    capabilities = require_model_capabilities(model)
    if not capabilities.text_output:
        raise ValueError(f"Model '{model}' does not support text generation")
    if has_image_input and not capabilities.image_input:
        raise ValueError(f"Model '{model}' does not support image input")
    if uses_tools and not capabilities.tools:
        raise ValueError(f"Model '{model}' does not support tool calls")
    if uses_search and not capabilities.search:
        raise ValueError(f"Model '{model}' does not support Google Search grounding")
    if uses_thinking and not capabilities.thinking:
        raise ValueError(f"Model '{model}' does not support thinking configuration")
    if stream and not capabilities.streaming:
        raise ValueError(f"Model '{model}' does not support streaming responses")
    return capabilities


def unsupported_generation_fields_for(model: str) -> tuple[str, ...]:
    return get_model_capabilities(model).unsupported_generation_fields