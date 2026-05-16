"""Application service layer for API handlers."""

from __future__ import annotations

import base64
import asyncio
import json
import logging
import tempfile
import time
import uuid
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from aistudio_api.application.chat_service import cleanup_files, encode_schema_to_wire, normalize_chat_request, normalize_gemini_request, normalize_openai_tools
from aistudio_api.application.chat_service import data_uri_to_file, url_to_file
from aistudio_api.application.validation import validate_number_range
from aistudio_api.domain.errors import AistudioError, AuthError, RequestError, UsageLimitExceeded
from aistudio_api.domain.model_capabilities import (
    DEFAULT_IMAGE_N,
    DEFAULT_IMAGE_RESPONSE_FORMAT,
    DEFAULT_IMAGE_SIZE,
    IMAGE_IGNORED_OPENAI_FIELDS,
    IMAGE_N_MAX,
    IMAGE_N_MIN,
    IMAGE_RESPONSE_FORMATS,
    IMAGE_UNSUPPORTED_OPENAI_FIELDS,
    get_model_capabilities,
    plan_image_generation,
    validate_chat_capabilities,
)
from aistudio_api.infrastructure.generated_images import GeneratedImageStore
from aistudio_api.infrastructure.gateway.client import AIStudioClient
from aistudio_api.infrastructure.gateway.wire_types import AistudioContent, AistudioPart, AistudioThinkingConfig, ThinkingLevel
from aistudio_api.api.responses import (
    chat_completion_response,
    new_chat_id,
    sse_chunk,
    sse_error,
    sse_usage_chunk,
    to_gemini_parts,
    to_gemini_usage_metadata,
    to_openai_tool_calls,
)
from aistudio_api.api.schemas import ChatRequest, GeminiGenerateContentRequest, ImagePromptOptimizationRequest, ImageRequest
from aistudio_api.api.state import runtime_state

logger = logging.getLogger("aistudio.server")

MAX_IMAGE_EDIT_INPUTS = 10


IMAGE_STYLE_TEMPLATES: dict[str, dict[str, str]] = {
    "none": {
        "label": "无模板",
        "description": "不追加固定风格，尽量保留原始表达。",
        "prompt_hint": "",
    },
    "photorealistic": {
        "label": "写实摄影",
        "description": "对应官方 photography / photorealistic 提示类别。",
        "prompt_hint": "Render as a photorealistic image with natural materials, believable lighting, camera/lens cues, depth of field, and high-detail textures.",
    },
    "comic": {
        "label": "漫画插画",
        "description": "对应 illustration / graphic art 提示类别。",
        "prompt_hint": "Render as a polished comic illustration with clean line art, expressive shapes, controlled colors, readable composition, and strong visual storytelling.",
    },
    "digital-art": {
        "label": "数字艺术",
        "description": "对应 digital art / concept art 提示类别。",
        "prompt_hint": "Render as cinematic digital art with polished art direction, stylized lighting, detailed environment design, and a high-quality finished look.",
    },
    "watercolor": {
        "label": "水彩",
        "description": "对应 painting / traditional media 提示类别。",
        "prompt_hint": "Render as watercolor artwork with translucent washes, soft edges, paper texture, organic color blending, and delicate hand-painted detail.",
    },
    "oil-painting": {
        "label": "油画",
        "description": "对应 painting / historical art references 提示类别。",
        "prompt_hint": "Render as an oil painting with visible brushwork, layered paint texture, rich value contrast, classical composition, and museum-quality finish.",
    },
    "anime": {
        "label": "动漫",
        "description": "对应 stylized illustration / animation 提示类别。",
        "prompt_hint": "Render in anime-inspired cel animation style with expressive characters, clean silhouettes, crisp shading, vivid but controlled colors, and cinematic framing.",
    },
    "3d-render": {
        "label": "3D 渲染",
        "description": "对应 3D / product visualization 提示类别。",
        "prompt_hint": "Render as a high-quality 3D scene with physically based materials, clean geometry, studio lighting, realistic shadows, and precise surface detail.",
    },
    "pixel-art": {
        "label": "像素艺术",
        "description": "对应 stylized illustration / game art 提示类别。",
        "prompt_hint": "Render as pixel art with a crisp low-resolution pixel grid, limited color palette, readable silhouettes, and retro game asset clarity.",
    },
}


IMAGE_PROMPT_OPTIMIZATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "options": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "special": {"type": "string"},
                    "prompt": {"type": "string"},
                },
                "required": ["title", "special", "prompt"],
            },
        }
    },
    "required": ["options"],
}


THINKING_LEVELS = {
    "low": ThinkingLevel.LOW,
    "medium": ThinkingLevel.MEDIUM,
    "high": ThinkingLevel.HIGH,
}


def _bad_request(message: str, error_type: str = "bad_request") -> HTTPException:
    return HTTPException(400, detail={"message": message, "type": error_type})


def parse_image_request(payload: Any) -> ImageRequest:
    try:
        return ImageRequest.model_validate(payload)
    except ValidationError as exc:
        fields = [".".join(str(part) for part in error["loc"]) for error in exc.errors() if error.get("loc")]
        if fields:
            message = f"Invalid image generation request field(s): {', '.join(fields)}. {exc.errors()[0]['msg']}"
        else:
            message = str(exc)
        raise _bad_request(message, "invalid_request_error") from exc


def _upstream_exception(exc: AistudioError) -> HTTPException:
    if isinstance(exc, AuthError):
        return HTTPException(401, detail={"message": str(exc), "type": "authentication_error"})
    if isinstance(exc, RequestError) and exc.status == 501:
        return HTTPException(501, detail={"message": exc.message or str(exc), "type": "unsupported_feature"})
    return HTTPException(502, detail={"message": str(exc), "type": "upstream_error"})


def _unsupported(message: str) -> HTTPException:
    return HTTPException(501, detail={"message": message, "type": "unsupported_feature"})


def _client_is_pure_http(client: AIStudioClient) -> bool:
    return bool(getattr(client, "is_pure_http", False))


def _pure_http_streaming_message() -> str:
    return "Pure HTTP mode is experimental and does not support streaming; disable AISTUDIO_USE_PURE_HTTP or use browser mode"


def _exception_message(exc: BaseException) -> str:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            return str(detail.get("message") or detail)
        return str(detail)
    if isinstance(exc, RequestError) and exc.message:
        return exc.message
    return str(exc)


def _openai_stream_error_detail(exc: BaseException) -> tuple[str, str, str | None]:
    message = _exception_message(exc)
    if isinstance(exc, RequestError) and exc.status == 501:
        return message, "unsupported_feature", "unsupported_feature"
    if isinstance(exc, AuthError):
        return message, "authentication_error", "authentication_error"
    if isinstance(exc, UsageLimitExceeded):
        return message, "rate_limit_exceeded", "rate_limit_exceeded"
    if isinstance(exc, AistudioError):
        return message, "upstream_error", "upstream_error"
    return message, "server_error", "server_error"


def _gemini_stream_error_payload(exc: BaseException) -> dict[str, Any]:
    message = _exception_message(exc)
    if isinstance(exc, RequestError) and exc.status == 501:
        return {"error": {"code": 501, "message": message, "status": "UNIMPLEMENTED"}}
    if isinstance(exc, AuthError):
        return {"error": {"code": 401, "message": message, "status": "UNAUTHENTICATED"}}
    if isinstance(exc, UsageLimitExceeded):
        return {"error": {"code": 429, "message": message, "status": "RESOURCE_EXHAUSTED"}}
    if isinstance(exc, AistudioError):
        return {"error": {"code": 502, "message": message, "status": "BAD_GATEWAY"}}
    return {"error": {"code": 500, "message": message, "status": "INTERNAL"}}


async def _request_disconnected(request: Request | None) -> bool:
    if request is None:
        return False
    try:
        return await request.is_disconnected()
    except Exception:
        return False


async def _close_async_iterator(iterator: Any) -> None:
    close = getattr(iterator, "aclose", None)
    if close is not None:
        await close()


def _merge_generation_overrides(*overrides: dict | None) -> dict | None:
    merged: dict[str, Any] = {}
    for override in overrides:
        if override:
            merged.update(override)
    return merged or None


def _schema_from_json_schema_format(response_format: dict[str, Any]) -> dict[str, Any]:
    schema_payload = response_format.get("json_schema")
    if schema_payload is not None:
        if not isinstance(schema_payload, dict):
            raise ValueError("response_format.json_schema must be an object")
        schema = schema_payload.get("schema")
        if isinstance(schema, dict):
            return schema
        if any(key in schema_payload for key in ("type", "properties", "$schema", "items")):
            return schema_payload
        raise ValueError("response_format.json_schema.schema must be an object")

    schema = response_format.get("schema")
    if isinstance(schema, dict):
        return schema
    raise ValueError("response_format json_schema requires a schema object")


def _response_format_overrides(response_format: dict[str, Any] | str | None) -> dict | None:
    if response_format is None:
        return None
    if isinstance(response_format, str):
        response_type = response_format.strip().lower()
        if response_type in ("", "text"):
            return None
        if response_type == "json_object":
            return {"response_mime_type": "application/json"}
        raise ValueError("response_format must be 'text', 'json_object', or an object")
    if not isinstance(response_format, dict):
        raise ValueError("response_format must be a JSON object")
    if "type" not in response_format and isinstance(response_format.get("format"), dict):
        return _response_format_overrides(response_format["format"])

    response_type = str(response_format.get("type") or "text").lower()
    if response_type == "text":
        return None
    if response_type == "json_object":
        return {"response_mime_type": "application/json"}
    if response_type == "json_schema":
        schema = _schema_from_json_schema_format(response_format)
        return {"response_mime_type": "application/json", "response_schema": encode_schema_to_wire(schema)}
    raise ValueError("response_format.type must be one of: text, json_object, json_schema")


def _validate_chat_request(req: ChatRequest) -> dict | None:
    validate_number_range("temperature", req.temperature, minimum=0, maximum=2)
    validate_number_range("top_p", req.top_p, minimum=0, maximum=1)
    validate_number_range("top_k", req.top_k, minimum=1, integer=True)
    validate_number_range("max_tokens", req.max_tokens, minimum=1, integer=True)
    return _response_format_overrides(req.response_format)


def _validate_image_model_chat_options(req: ChatRequest) -> None:
    unsupported = []
    if req.temperature is not None:
        unsupported.append("temperature")
    if req.top_p is not None:
        unsupported.append("top_p")
    if req.top_k is not None:
        unsupported.append("top_k")
    if req.max_tokens is not None:
        unsupported.append("max_tokens")
    if req.tools:
        unsupported.append("tools")
    if req.grounding:
        unsupported.append("grounding")
    if _explicit_thinking_enabled(req.thinking):
        unsupported.append("thinking")
    if req.safety_off:
        unsupported.append("safety_off")
    if req.response_format is not None:
        unsupported.append("response_format")
    if unsupported:
        fields = ", ".join(unsupported)
        raise ValueError(f"Image generation models do not support chat field(s): {fields}")


def _explicit_thinking_enabled(value: str | bool | None) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return value.lower() not in ("off", "false", "0", "none")


def _thinking_enabled(value: str | bool | None) -> bool:
    if value is None:
        return True
    return _explicit_thinking_enabled(value)


def _thinking_overrides(value: str | bool | None) -> dict | None:
    if value is None or isinstance(value, bool):
        return None
    normalized = value.lower()
    if normalized in ("off", "false", "0", "none"):
        return None
    level = THINKING_LEVELS.get(normalized)
    if level is None:
        raise ValueError("thinking must be one of: off, low, medium, high")
    return {"thinking_config": AistudioThinkingConfig(level).to_wire(), "request_flag": 1}


def _style_template_for(template_id: str) -> dict[str, str]:
    template = IMAGE_STYLE_TEMPLATES.get((template_id or "none").strip())
    if template is None:
        supported = ", ".join(IMAGE_STYLE_TEMPLATES)
        raise ValueError(f"style_template must be one of: {supported}")
    return template


def _optimizer_system_prompt() -> str:
    return (
        "You are an expert prompt optimizer for image generation models. "
        "Return exactly three optimized prompt options as JSON matching the requested schema. "
        "Each option must preserve the user's intent, make the visual scene concrete, and be directly usable as an image prompt. "
        "Write titles and special notes in Chinese. Write optimized prompts in the user's language unless technical visual modifiers are clearer in English. "
        "Do not include markdown, explanations, or extra keys."
    )


def _optimizer_user_prompt(raw_prompt: str, style_template_id: str, style_template: dict[str, str]) -> str:
    style_hint = style_template.get("prompt_hint") or "No fixed style template. Preserve the original style direction."
    return (
        f"原始提示词:\n{raw_prompt}\n\n"
        f"风格模板: {style_template['label']} ({style_template_id})\n"
        f"模板说明: {style_template['description']}\n"
        f"模板提示: {style_hint}\n\n"
        "请输出 3 个优化版本:\n"
        "1. 一个强调主体与构图的稳定版本。\n"
        "2. 一个强调光线、材质与质感的精修版本。\n"
        "3. 一个强调氛围、镜头感或创意变化的版本。\n"
        "每个版本都必须包含 title、special、prompt。"
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("optimizer response was not valid JSON") from None
        data = json.loads(cleaned[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("optimizer response JSON must be an object")
    return data


def _normalize_prompt_optimization_options(payload: dict[str, Any]) -> list[dict[str, str]]:
    raw_options = payload.get("options")
    if not isinstance(raw_options, list) or len(raw_options) != 3:
        raise ValueError("optimizer response must include exactly 3 options")
    options: list[dict[str, str]] = []
    for index, item in enumerate(raw_options, start=1):
        if not isinstance(item, dict):
            raise ValueError("optimizer response options must be objects")
        title = str(item.get("title") or f"版本 {index}").strip()
        special = str(item.get("special") or item.get("note") or "").strip()
        prompt = str(item.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("optimizer response option prompt is required")
        options.append({"title": title, "special": special, "prompt": prompt})
    return options


async def handle_image_prompt_optimization(req: ImagePromptOptimizationRequest, client: AIStudioClient) -> dict[str, Any]:
    raw_prompt = req.prompt.strip()
    if not raw_prompt:
        raise _bad_request("prompt is required", "invalid_request_error")
    try:
        style_template = _style_template_for(req.style_template)
        capabilities = get_model_capabilities(req.model, strict=True)
    except ValueError as exc:
        raise _bad_request(str(exc), "invalid_request_error") from exc
    if not capabilities.text_output or capabilities.image_output:
        raise _bad_request(f"Model '{req.model}' must be a text prompt optimization model", "invalid_request_error")
    thinking = req.thinking
    if not capabilities.thinking:
        thinking = "off"

    chat_req = ChatRequest(
        model=capabilities.id,
        messages=[
            {"role": "system", "content": _optimizer_system_prompt()},
            {"role": "user", "content": _optimizer_user_prompt(raw_prompt, req.style_template, style_template)},
        ],
        thinking=thinking,
        temperature=0.8,
        response_format={"type": "json_schema", "json_schema": {"schema": IMAGE_PROMPT_OPTIMIZATION_SCHEMA}},
    )
    if not capabilities.structured_output:
        chat_req.response_format = None

    chat_response = await handle_chat(chat_req, client)
    content = _chat_text(chat_response)
    try:
        options = _normalize_prompt_optimization_options(_extract_json_object(content))
    except ValueError as exc:
        raise HTTPException(502, detail={"message": str(exc), "type": "upstream_error"}) from exc
    return {
        "object": "image_prompt_optimization",
        "model": capabilities.id,
        "style_template": req.style_template,
        "style_label": style_template["label"],
        "options": options,
        "usage": chat_response.get("usage"),
    }


def _merge_usage(total: dict, usage: dict | None) -> dict:
    if not usage:
        return total
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, int):
            total[key] = total.get(key, 0) + value
    completion_details = usage.get("completion_tokens_details")
    if isinstance(completion_details, dict):
        total_details = total.setdefault("completion_tokens_details", {})
        for key, value in completion_details.items():
            if isinstance(value, int):
                total_details[key] = total_details.get(key, 0) + value
    return total


def _normalize_image_response_format(response_format: str | None) -> str:
    normalized = (response_format or DEFAULT_IMAGE_RESPONSE_FORMAT).strip().lower()
    if normalized not in IMAGE_RESPONSE_FORMATS:
        supported = ", ".join(IMAGE_RESPONSE_FORMATS)
        raise ValueError(f"response_format must be one of: {supported}")
    return normalized


def _validate_unsupported_image_fields(req: ImageRequest) -> None:
    unsupported = [field for field in IMAGE_UNSUPPORTED_OPENAI_FIELDS if getattr(req, field, None) is not None]
    if not unsupported:
        return
    fields = ", ".join(unsupported)
    supported = "prompt, model, n, size, response_format, images, timeout"
    ignored = ", ".join(IMAGE_IGNORED_OPENAI_FIELDS)
    raise ValueError(
        f"Unsupported image generation field(s): {fields}. Supported fields: {supported}. "
        f"Compatibility-only ignored field(s): {ignored}"
    )


def _image_data_url(mime_type: str | None, b64: str) -> str:
    mime = mime_type or "image/png"
    return f"data:{mime};base64,{b64}"


def _format_image_items(items: list[dict[str, Any]], response_format: str) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = []
    for item in items:
        if response_format == "url":
            data.append(
                {
                    "url": item["url"],
                    "b64_json": item["b64_json"],
                    "revised_prompt": item["revised_prompt"],
                    "id": item.get("id"),
                    "path": item.get("path"),
                    "delete_url": item.get("delete_url"),
                    "mime_type": item.get("mime_type"),
                    "size_bytes": item.get("size_bytes"),
                }
            )
        else:
            data.append(
                {
                    "b64_json": item["b64_json"],
                    "revised_prompt": item["revised_prompt"],
                    "url": item.get("url"),
                    "id": item.get("id"),
                    "path": item.get("path"),
                    "delete_url": item.get("delete_url"),
                    "mime_type": item.get("mime_type"),
                    "size_bytes": item.get("size_bytes"),
                }
            )
    return data


def _image_chat_content(data: list[dict[str, Any]]) -> str:
    lines = []
    for index, item in enumerate(data, start=1):
        image_url = item.get("url")
        if not image_url and item.get("b64_json"):
            image_url = _image_data_url("image/png", item["b64_json"])
        if image_url:
            lines.append(f"![generated image {index}]({image_url})")
    return "\n\n".join(lines)


def _image_reference_url(value: Any) -> str:
    if isinstance(value, str):
        return value
    url = getattr(value, "url", None)
    if isinstance(url, str):
        return url
    raise ValueError("images[] must be a data URI, HTTP URL, or object with url")


def _image_request_images_to_files(images: list[Any] | None) -> list[str]:
    if not images:
        return []
    if len(images) > MAX_IMAGE_EDIT_INPUTS:
        raise ValueError(f"images supports at most {MAX_IMAGE_EDIT_INPUTS} items")

    paths: list[str] = []
    tmp_dir = tempfile.gettempdir()
    try:
        for index, image in enumerate(images):
            url = _image_reference_url(image).strip()
            if not url:
                raise ValueError(f"images[{index}].url is required")
            if url.startswith("data:"):
                paths.append(data_uri_to_file(url, tmp_dir=tmp_dir))
            elif url.startswith("http://") or url.startswith("https://"):
                paths.append(url_to_file(url, tmp_dir=tmp_dir))
            else:
                raise ValueError(f"images[{index}].url must be a data URI or HTTP URL")
        return paths
    except Exception:
        cleanup_files(paths)
        raise


def _is_image_output_chat_model(model: str) -> bool:
    try:
        return get_model_capabilities(model, strict=True).image_output
    except ValueError:
        return False


def _chat_image_request(req: ChatRequest) -> tuple[ImageRequest, list[str]]:
    normalized = normalize_chat_request(req.messages, req.model)
    cleanup_paths = list(normalized["cleanup_paths"])
    if normalized.get("file_input_mime_types"):
        cleanup_files(cleanup_paths)
        raise ValueError("Image generation through chat completions supports text prompts only")
    if normalized["capture_images"]:
        cleanup_files(cleanup_paths)
        raise ValueError("Image generation through chat completions supports text prompts only")
    return (
        ImageRequest(
            prompt=normalized["capture_prompt"],
            model=normalized["model"],
            n=DEFAULT_IMAGE_N,
            size=DEFAULT_IMAGE_SIZE,
            response_format="url",
        ),
        cleanup_paths,
    )


def _validate_image_request(req: ImageRequest):
    _validate_unsupported_image_fields(req)
    if not req.prompt or not req.prompt.strip():
        raise ValueError("prompt is required")
    if req.n < IMAGE_N_MIN:
        raise ValueError(f"n must be at least {IMAGE_N_MIN}")
    if req.n > IMAGE_N_MAX:
        raise ValueError(f"n must be {IMAGE_N_MAX} or less")
    validate_number_range("timeout", req.timeout, minimum=1, integer=True)
    response_format = _normalize_image_response_format(req.response_format)
    return plan_image_generation(req.model, req.size), response_format


async def _try_switch_account(model: str | None = None, *, require_preferred: bool = False) -> bool:
    """尝试切换到下一个可用账号。返回是否成功切换。"""
    rotator = runtime_state.rotator
    if rotator is None:
        return False

    # 获取下一个账号
    next_account = await rotator.get_next_account(model, require_preferred=require_preferred)
    if next_account is None:
        return False

    account_service = runtime_state.account_service
    client = runtime_state.client

    if not all([account_service, client]):
        return False

    # 切换账号时清掉 snapshot，避免复用旧页面态。
    result = await account_service.activate_account(
        next_account.id,
        client._session,
        runtime_state.snapshot_cache,
        None,  # skip lock — caller already holds it
        keep_snapshot_cache=False,
    )
    if result is not None:
        logger.info("Account switched for model=%s reason=%s", model or "<any>", getattr(rotator, "last_selection_reason", None))
    return result is not None


async def _ensure_account_for_model(model: str | None) -> None:
    account_service = runtime_state.account_service
    rotator = runtime_state.rotator
    if account_service is None or rotator is None:
        return

    active = account_service.get_active_account()
    if active is None or getattr(active, "is_isolated", False):
        await _try_switch_account(model)
        return

    if rotator.model_prefers_premium(model) and not getattr(active, "is_premium", False):
        if rotator.has_available_preferred_account(model):
            await _try_switch_account(model, require_preferred=True)
            return
        logger.warning("Image model is using a non-premium account because no healthy Pro/Ultra account is available")


def health_response() -> dict:
    busy_lock = runtime_state.busy_lock
    return {"status": "ok", "busy": busy_lock.locked() if busy_lock else False}


def stats_response() -> dict:
    stats = dict(runtime_state.model_stats)
    image_sizes: dict[str, int] = {}
    for value in stats.values():
        for size, count in (value.get("image_sizes") or {}).items():
            image_sizes[size] = image_sizes.get(size, 0) + count
    totals = {
        "requests": sum(s.get("requests", 0) for s in stats.values()),
        "success": sum(s.get("success", 0) for s in stats.values()),
        "rate_limited": sum(s.get("rate_limited", 0) for s in stats.values()),
        "errors": sum(s.get("errors", 0) for s in stats.values()),
        "prompt_tokens": sum(s.get("prompt_tokens", 0) for s in stats.values()),
        "completion_tokens": sum(s.get("completion_tokens", 0) for s in stats.values()),
        "total_tokens": sum(s.get("total_tokens", 0) for s in stats.values()),
        "image_sizes": image_sizes,
        "image_total": sum(image_sizes.values()),
    }
    return {"models": stats, "totals": totals}


def _coerce_openai_content_blocks(content: Any) -> str | list[dict[str, Any]]:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        raise ValueError("message content must be a string or content block array")
    blocks: list[dict[str, Any]] = []
    for block in content:
        if isinstance(block, str):
            blocks.append({"type": "text", "text": block})
            continue
        if not isinstance(block, dict):
            raise ValueError("message content blocks must be objects")
        block_type = str(block.get("type") or "text")
        if block_type in ("text", "input_text"):
            text = block.get("text")
            if not isinstance(text, str):
                raise ValueError("text content blocks require text")
            blocks.append({"type": "text", "text": text})
        elif block_type in ("image_url", "input_image"):
            image_url = block.get("image_url") or block.get("url")
            if isinstance(image_url, dict):
                image_url = image_url.get("url")
            if not isinstance(image_url, str) or not image_url:
                raise ValueError("image content blocks require image_url")
            blocks.append({"type": "image_url", "image_url": {"url": image_url}})
        elif block_type == "image":
            source = block.get("source")
            if not isinstance(source, dict):
                raise ValueError("image content blocks require source")
            source_type = source.get("type")
            if source_type == "base64":
                media_type = source.get("media_type") or "image/png"
                data = source.get("data")
                if not isinstance(data, str) or not data:
                    raise ValueError("image source.data is required")
                blocks.append({"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{data}"}})
            elif source_type == "url":
                url = source.get("url")
                if not isinstance(url, str) or not url:
                    raise ValueError("image source.url is required")
                blocks.append({"type": "image_url", "image_url": {"url": url}})
            else:
                raise ValueError("image source.type must be base64 or url")
        elif block_type in ("tool_result", "input_tool_result"):
            content_value = block.get("content", "")
            if isinstance(content_value, str):
                blocks.append({"type": "text", "text": content_value})
            elif isinstance(content_value, list):
                blocks.extend(_coerce_openai_content_blocks(content_value))
            else:
                blocks.append({"type": "text", "text": json.dumps(content_value, ensure_ascii=False)})
        elif block_type in ("file", "input_file"):
            file_data = block.get("file_data") or block.get("data")
            if not isinstance(file_data, str) or not file_data:
                raise ValueError("file content blocks require file_data")
            blocks.append(
                {
                    "type": "file",
                    "file": {
                        "file_data": file_data,
                        "filename": block.get("filename") or block.get("name") or "upload",
                        "mime_type": block.get("mime_type") or block.get("media_type") or "application/octet-stream",
                    },
                }
            )
        else:
            raise ValueError(f"unsupported content block type: {block_type}")
    return blocks


def _messages_from_responses_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    instructions = payload.get("instructions")
    if isinstance(instructions, str) and instructions.strip():
        messages.append({"role": "system", "content": instructions})

    input_value = payload.get("input")
    if isinstance(input_value, str):
        messages.append({"role": "user", "content": input_value})
        return messages
    if not isinstance(input_value, list) or not input_value:
        raise ValueError("input must be a non-empty string or message array")

    for item in input_value:
        if isinstance(item, str):
            messages.append({"role": "user", "content": item})
            continue
        if not isinstance(item, dict):
            raise ValueError("input array items must be strings or objects")
        item_type = str(item.get("type") or "message")
        if item_type == "message" or "role" in item:
            role = str(item.get("role") or "user")
            messages.append({"role": role, "content": _coerce_openai_content_blocks(item.get("content", ""))})
        elif item_type in ("input_text", "text"):
            text = item.get("text")
            if not isinstance(text, str):
                raise ValueError("input_text items require text")
            messages.append({"role": "user", "content": text})
        elif item_type == "input_image":
            messages.append({"role": "user", "content": _coerce_openai_content_blocks([item])})
        elif item_type in ("input_file", "file"):
            messages.append({"role": "user", "content": _coerce_openai_content_blocks([item])})
        else:
            raise ValueError(f"unsupported input item type: {item_type}")
    return messages


def _chat_text(chat_response: dict[str, Any]) -> str:
    message = _chat_message(chat_response)
    content = message.get("content", "")
    return content if isinstance(content, str) else ""


def _chat_message(chat_response: dict[str, Any]) -> dict[str, Any]:
    choices = chat_response.get("choices") if isinstance(chat_response, dict) else None
    if not choices:
        return {}
    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    return message if isinstance(message, dict) else {}


def _chat_tool_calls(chat_response: dict[str, Any]) -> list[dict[str, Any]]:
    tool_calls = _chat_message(chat_response).get("tool_calls")
    return tool_calls if isinstance(tool_calls, list) else []


def _parse_tool_arguments(arguments: Any) -> Any:
    if isinstance(arguments, str):
        try:
            return json.loads(arguments)
        except json.JSONDecodeError:
            return arguments
    return arguments if arguments is not None else {}


def _responses_output_items(chat_response: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    text = _chat_text(chat_response)
    if text:
        output.append(
            {
                "id": f"msg_{uuid.uuid4().hex[:24]}",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        )
    for tool_call in _chat_tool_calls(chat_response):
        function = tool_call.get("function") if isinstance(tool_call, dict) else None
        if not isinstance(function, dict):
            continue
        output.append(
            {
                "id": f"fc_{uuid.uuid4().hex[:24]}",
                "type": "function_call",
                "status": "completed",
                "call_id": tool_call.get("id"),
                "name": function.get("name") or "unknown",
                "arguments": function.get("arguments") or "{}",
            }
        )
    if output:
        return output
    return [
        {
            "id": f"msg_{uuid.uuid4().hex[:24]}",
            "type": "message",
            "status": "completed",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "", "annotations": []}],
        }
    ]


def _message_content_blocks(chat_response: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    text = _chat_text(chat_response)
    if text:
        blocks.append({"type": "text", "text": text})
    for tool_call in _chat_tool_calls(chat_response):
        function = tool_call.get("function") if isinstance(tool_call, dict) else None
        if not isinstance(function, dict):
            continue
        blocks.append(
            {
                "type": "tool_use",
                "id": tool_call.get("id"),
                "name": function.get("name") or "unknown",
                "input": _parse_tool_arguments(function.get("arguments")),
            }
        )
    return blocks or [{"type": "text", "text": ""}]


def _messages_tools_from_payload(tools: Any) -> Any:
    if not tools:
        return None
    if not isinstance(tools, list):
        raise ValueError("tools must be an array")
    converted = []
    for tool in tools:
        if not isinstance(tool, dict):
            raise ValueError("tools items must be objects")
        if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
            converted.append(tool)
            continue
        if tool.get("type") not in (None, "function"):
            converted.append(tool)
            continue
        name = tool.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("tools[].name is required")
        parameters = tool.get("input_schema") if isinstance(tool.get("input_schema"), dict) else None
        if parameters is None and isinstance(tool.get("parameters"), dict):
            parameters = tool.get("parameters")
        converted.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.get("description") if isinstance(tool.get("description"), str) else None,
                    "parameters": parameters,
                },
            }
        )
    return converted or None


async def handle_openai_responses(payload: dict[str, Any], client: AIStudioClient) -> dict[str, Any]:
    if not payload.get("model"):
        raise _bad_request("model is required", "invalid_request_error")
    if payload.get("stream"):
        raise _bad_request("/v1/responses streaming is not supported yet; use /v1/chat/completions for streaming", "invalid_request_error")
    response_format = payload.get("response_format")
    text_config = payload.get("text")
    if response_format is None and isinstance(text_config, dict):
        response_format = text_config.get("format")
    try:
        chat_req = ChatRequest(
            model=str(payload["model"]),
            messages=_messages_from_responses_payload(payload),
            temperature=payload.get("temperature"),
            top_p=payload.get("top_p"),
            max_tokens=payload.get("max_output_tokens") or payload.get("max_tokens"),
            tools=_messages_tools_from_payload(payload.get("tools")),
            thinking=payload.get("thinking"),
            response_format=response_format,
        )
    except (ValueError, ValidationError) as exc:
        raise _bad_request(str(exc), "invalid_request_error") from exc
    chat_response = await handle_chat(chat_req, client)
    text = _chat_text(chat_response)
    return {
        "id": f"resp_{uuid.uuid4().hex[:24]}",
        "object": "response",
        "created_at": int(time.time()),
        "status": "completed",
        "model": chat_response.get("model", payload["model"]),
        "output": _responses_output_items(chat_response),
        "output_text": text,
        "usage": chat_response.get("usage"),
    }


def _messages_from_messages_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    system = payload.get("system")
    if isinstance(system, str) and system.strip():
        messages.append({"role": "system", "content": system})
    raw_messages = payload.get("messages")
    if not isinstance(raw_messages, list) or not raw_messages:
        raise ValueError("messages must be a non-empty array")
    for item in raw_messages:
        if not isinstance(item, dict):
            raise ValueError("messages items must be objects")
        messages.append(
            {
                "role": str(item.get("role") or "user"),
                "content": _coerce_openai_content_blocks(item.get("content", "")),
            }
        )
    return messages


async def handle_messages(payload: dict[str, Any], client: AIStudioClient) -> dict[str, Any]:
    if not payload.get("model"):
        raise _bad_request("model is required", "invalid_request_error")
    if payload.get("stream"):
        raise _bad_request("/v1/messages streaming is not supported yet; use /v1/chat/completions for streaming", "invalid_request_error")
    try:
        chat_req = ChatRequest(
            model=str(payload["model"]),
            messages=_messages_from_messages_payload(payload),
            temperature=payload.get("temperature"),
            top_p=payload.get("top_p"),
            max_tokens=payload.get("max_tokens"),
            tools=_messages_tools_from_payload(payload.get("tools")),
            response_format=payload.get("response_format"),
        )
    except (ValueError, ValidationError) as exc:
        raise _bad_request(str(exc), "invalid_request_error") from exc
    chat_response = await handle_chat(chat_req, client)
    usage = chat_response.get("usage") or {}
    return {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "model": chat_response.get("model", payload["model"]),
        "content": _message_content_blocks(chat_response),
        "stop_reason": "tool_use" if _chat_tool_calls(chat_response) else "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


def gemini_model_dict(model_id: str) -> dict[str, Any]:
    metadata = get_model_capabilities(model_id, strict=True).to_model_dict()
    capabilities = metadata["capabilities"]
    methods = ["generateContent", "countTokens"]
    if capabilities.get("streaming"):
        methods.append("streamGenerateContent")
    return {
        "name": f"models/{metadata['id']}",
        "version": "001",
        "displayName": metadata["id"],
        "description": "AI Studio replay-backed model metadata",
        "inputTokenLimit": 1048576,
        "outputTokenLimit": 65536,
        "supportedGenerationMethods": methods,
    }


def list_gemini_models_response() -> dict[str, Any]:
    from aistudio_api.domain.model_capabilities import MODEL_CAPABILITIES

    return {"models": [gemini_model_dict(model_id) for model_id in MODEL_CAPABILITIES]}


def _estimate_text_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _estimate_content_tokens(contents: list[AistudioContent]) -> int:
    total = 0
    for content in contents:
        for part in content.parts:
            if part.text is not None:
                total += _estimate_text_tokens(part.text)
            elif part.inline_data is not None:
                total += 258 + max(1, len(part.inline_data[1]) // 1024)
    return total


def gemini_count_tokens_response(model_path: str, payload: dict[str, Any]) -> dict[str, Any]:
    request_payload = payload.get("generateContentRequest") if isinstance(payload.get("generateContentRequest"), dict) else payload
    req = GeminiGenerateContentRequest.model_validate(request_payload)
    normalized = None
    try:
        normalized = normalize_gemini_request(req, model_path, stream=False)
        total_tokens = _estimate_content_tokens(normalized["contents"])
        if normalized.get("system_instruction") is not None:
            total_tokens += _estimate_content_tokens([normalized["system_instruction"]])
        return {"totalTokens": total_tokens}
    finally:
        if normalized is not None:
            cleanup_files(normalized["cleanup_paths"])


def _build_chat_image_streaming_response(
    image_req: ImageRequest,
    client: AIStudioClient,
    cleanup_paths: list[str],
    *,
    include_usage: bool,
    request: Request | None = None,
) -> StreamingResponse:
    async def stream_response():
        try:
            if await _request_disconnected(request):
                logger.info("Chat image stream disconnected before downstream call")
                return
            chat_id = new_chat_id()
            image_response = await handle_image_generation(image_req, client)
            if await _request_disconnected(request):
                logger.info("Chat image stream disconnected before response write")
                return
            content = _image_chat_content(image_response["data"])
            if content:
                yield sse_chunk(chat_id, image_req.model, content, include_usage=include_usage)
            yield sse_chunk(chat_id, image_req.model, "", finish="stop", include_usage=include_usage)
            if include_usage:
                yield sse_usage_chunk(chat_id, image_req.model)
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            logger.info("Chat image stream cancelled by client")
            raise
        except HTTPException as exc:
            detail = exc.detail.get("message") if isinstance(exc.detail, dict) else str(exc.detail)
            yield sse_error(detail)
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.error("Chat image stream error: %s", exc, exc_info=True)
            message, error_type, code = _openai_stream_error_detail(exc)
            yield sse_error(message, error_type=error_type, code=code)
            yield "data: [DONE]\n\n"
        finally:
            cleanup_files(cleanup_paths)

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def handle_chat(req: ChatRequest, client: AIStudioClient, request: Request | None = None):
    try:
        response_format_overrides = _validate_chat_request(req)
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc

    busy_lock = runtime_state.busy_lock
    if busy_lock is None:
        raise HTTPException(503, detail={"message": "Server not ready", "type": "service_unavailable"})
    if busy_lock.locked():
        raise HTTPException(429, detail={"message": "Server is busy", "type": "rate_limit_exceeded"})
    if req.stream and _client_is_pure_http(client):
        raise _unsupported(_pure_http_streaming_message())

    if _is_image_output_chat_model(req.model):
        cleanup_paths: list[str] = []
        try:
            _validate_image_model_chat_options(req)
            image_req, cleanup_paths = _chat_image_request(req)
            if req.stream:
                include_usage = True
                if req.stream_options is not None:
                    include_usage = req.stream_options.include_usage
                return _build_chat_image_streaming_response(image_req, client, cleanup_paths, include_usage=include_usage, request=request)

            image_response = await handle_image_generation(image_req, client)
            return chat_completion_response(
                model=image_req.model,
                content=_image_chat_content(image_response["data"]),
            )
        except ValueError as exc:
            raise _bad_request(str(exc)) from exc
        finally:
            if not req.stream:
                cleanup_files(cleanup_paths)

    max_retries = 3  # 最多重试次数
    last_error = None

    for attempt in range(max_retries):
        async with busy_lock:
            model = req.model
            tmp_files: list[str] = []

            try:
                normalized = normalize_chat_request(req.messages, req.model)
                model = normalized["model"]
                tmp_files = list(normalized["cleanup_paths"])
                tools = normalize_openai_tools(req.tools)
                has_image_input = bool(normalized["capture_images"])
                file_input_mime_types = tuple(normalized.get("file_input_mime_types") or ())
                validate_chat_capabilities(
                    model,
                    has_image_input=has_image_input,
                    has_file_input=bool(file_input_mime_types),
                    file_input_mime_types=file_input_mime_types,
                    uses_tools=bool(req.tools),
                    uses_search=bool(req.grounding),
                    uses_thinking=_explicit_thinking_enabled(req.thinking),
                    stream=req.stream,
                    uses_structured_output=response_format_overrides is not None,
                )
                if attempt == 0:
                    await _ensure_account_for_model(model)

                logger.info(
                    "Chat: model=%s, contents=%s, capture_prompt=%s..., images=%s, stream=%s, attempt=%d",
                    model,
                    len(normalized["contents"]),
                    normalized["capture_prompt"][:50],
                    len(normalized["capture_images"]),
                    req.stream,
                    attempt + 1,
                )

                if req.grounding:
                    from aistudio_api.infrastructure.gateway.request_rewriter import TOOLS_TEMPLATES
                    tools = list(tools or [])
                    tools.append(TOOLS_TEMPLATES["google_search"])

                # Gemma 4 默认开启 Google Search
                if tools is None and any(m in model for m in ("gemma-4-26b-a4b-it", "gemma-4-31b-it")):
                    from aistudio_api.infrastructure.gateway.request_rewriter import TOOLS_TEMPLATES
                    tools = [TOOLS_TEMPLATES["google_search"]]

                generation_config_overrides = _merge_generation_overrides(
                    response_format_overrides,
                    _thinking_overrides(req.thinking),
                )
                enable_thinking = _thinking_enabled(req.thinking)

                if req.stream:
                    include_usage = True
                    if req.stream_options is not None:
                        include_usage = req.stream_options.include_usage
                    return _build_streaming_response(
                        client=client,
                        capture_prompt=normalized["capture_prompt"],
                        model=model,
                        capture_images=normalized["capture_images"] if normalized["capture_images"] else None,
                        contents=normalized["contents"],
                        system_instruction=normalized["system_instruction"],
                        cleanup_paths=tmp_files,
                        include_usage=include_usage,
                        temperature=req.temperature,
                        top_p=req.top_p,
                        top_k=req.top_k,
                        max_tokens=req.max_tokens,
                        tools=tools,
                        generation_config_overrides=generation_config_overrides,
                        safety_off=bool(req.safety_off),
                        enable_thinking=enable_thinking,
                        sanitize_plain_text=response_format_overrides is None,
                        request=request,
                    )

                output = await client.generate_content(
                    model=model,
                    capture_prompt=normalized["capture_prompt"],
                    capture_images=normalized["capture_images"] if normalized["capture_images"] else None,
                    contents=normalized["contents"],
                    system_instruction_content=(
                        AistudioContent(role="user", parts=[AistudioPart(text=normalized["system_instruction"])])
                        if normalized["system_instruction"]
                        else None
                    ),
                    temperature=req.temperature,
                    top_p=req.top_p,
                    top_k=req.top_k,
                    max_tokens=req.max_tokens,
                    tools=tools,
                    generation_config_overrides=generation_config_overrides,
                    safety_off=bool(req.safety_off),
                    enable_thinking=enable_thinking,
                    sanitize_plain_text=response_format_overrides is None,
                )

                # 记录成功
                rotator = runtime_state.rotator
                if rotator:
                    account = runtime_state.account_service.get_active_account() if runtime_state.account_service else None
                    if account:
                        rotator.record_success(account.id)

                runtime_state.record(model, "success", output.usage)
                return chat_completion_response(
                    model=model,
                    content=output.text,
                    thinking=output.thinking,
                    usage=output.usage,
                    function_calls=output.function_calls,
                )
            except UsageLimitExceeded as exc:
                runtime_state.record(model, "rate_limited")
                last_error = exc

                # 记录限流
                rotator = runtime_state.rotator
                if rotator:
                    account = runtime_state.account_service.get_active_account() if runtime_state.account_service else None
                    if account:
                        rotator.record_rate_limited(account.id)

                # 尝试切换账号
                if await _try_switch_account(model):
                    logger.info("429 限流，已切换账号，重试 %d/%d", attempt + 1, max_retries)
                    continue
                else:
                    logger.warning("429 限流，无法切换账号")
                    raise HTTPException(429, detail={"message": str(exc), "type": "rate_limit_exceeded"}) from exc
            except ValueError as exc:
                raise _bad_request(str(exc)) from exc
            except (AuthError, RequestError) as exc:
                runtime_state.record(model, "errors")
                rotator = runtime_state.rotator
                if rotator:
                    account = runtime_state.account_service.get_active_account() if runtime_state.account_service else None
                    if account:
                        rotator.record_error(account.id)
                raise _upstream_exception(exc) from exc
            except AistudioError as exc:
                runtime_state.record(model, "errors")
                rotator = runtime_state.rotator
                if rotator:
                    account = runtime_state.account_service.get_active_account() if runtime_state.account_service else None
                    if account:
                        rotator.record_error(account.id)
                raise _upstream_exception(exc) from exc
            except Exception as exc:
                runtime_state.record(model, "errors")
                logger.error("Chat error: %s", exc, exc_info=True)
                raise HTTPException(500, detail={"message": str(exc), "type": "server_error"}) from exc
            finally:
                if not req.stream:
                    cleanup_files(tmp_files)

    # 所有重试都失败
    raise HTTPException(429, detail={"message": str(last_error), "type": "rate_limit_exceeded"}) from last_error


async def handle_image_generation(req: ImageRequest, client: AIStudioClient):
    busy_lock = runtime_state.busy_lock
    if busy_lock is None:
        raise HTTPException(503, detail={"message": "Server not ready", "type": "service_unavailable"})
    if busy_lock.locked():
        raise HTTPException(429, detail={"message": "Server is busy", "type": "rate_limit_exceeded"})

    try:
        image_plan, response_format = _validate_image_request(req)
        image_paths = _image_request_images_to_files(req.images)
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc

    max_retries = 3
    last_error = None
    image_store = GeneratedImageStore()
    try:
        for attempt in range(max_retries):
            async with busy_lock:
                items: list[dict[str, Any]] = []
                try:
                    if attempt == 0:
                        await _ensure_account_for_model(image_plan.model)
                    logger.info(
                        "Image: model=%s, size=%s, n=%d, prompt=%s..., images=%d, attempt=%d",
                        image_plan.model,
                        image_plan.size,
                        req.n,
                        req.prompt[:50],
                        len(image_paths),
                        attempt + 1,
                    )
                    usage_total: dict = {}
                    created = int(time.time())
                    for _ in range(req.n):
                        image_kwargs = {
                            "prompt": image_plan.prompt_for(req.prompt),
                            "model": image_plan.model,
                            "generation_config_overrides": image_plan.generation_config_overrides,
                        }
                        if image_paths:
                            image_kwargs["images"] = image_paths
                        if req.timeout is not None:
                            image_kwargs["timeout"] = req.timeout
                        output = await client.generate_image(**image_kwargs)
                        if not output.images:
                            raise RequestError(0, "AI Studio returned no image data")
                        _merge_usage(usage_total, output.usage)
                        for img in output.images:
                            b64 = base64.b64encode(img.data).decode("ascii")
                            persisted = image_store.save(img.data, img.mime, created_at=created)
                            items.append(
                                {
                                    "b64_json": b64,
                                    "url": persisted.url,
                                    "revised_prompt": output.text or "",
                                    "id": persisted.id,
                                    "path": persisted.path,
                                    "delete_url": persisted.delete_url,
                                    "mime_type": persisted.mime_type,
                                    "size_bytes": persisted.size,
                                }
                            )

                    # 记录成功
                    rotator = runtime_state.rotator
                    if rotator:
                        account = runtime_state.account_service.get_active_account() if runtime_state.account_service else None
                        if account:
                            rotator.record_success(account.id, image_size=image_plan.size, image_count=len(items))

                    runtime_state.record(image_plan.model, "success", usage_total, image_size=image_plan.size, image_count=len(items))
                    return {"created": created, "data": _format_image_items(items, response_format)}
                except UsageLimitExceeded as exc:
                    _cleanup_persisted_image_items(image_store, items)
                    runtime_state.record(image_plan.model, "rate_limited")
                    last_error = exc

                    # 记录限流
                    rotator = runtime_state.rotator
                    if rotator:
                        account = runtime_state.account_service.get_active_account() if runtime_state.account_service else None
                        if account:
                            rotator.record_rate_limited(account.id)

                    # 尝试切换账号
                    if await _try_switch_account(image_plan.model):
                        logger.info("Image 429 限流，已切换账号，重试 %d/%d", attempt + 1, max_retries)
                        continue
                    else:
                        logger.warning("Image 429 限流，无法切换账号")
                        raise HTTPException(429, detail={"message": str(exc), "type": "rate_limit_exceeded"}) from exc
                except (AuthError, RequestError) as exc:
                    _cleanup_persisted_image_items(image_store, items)
                    runtime_state.record(image_plan.model, "errors")
                    rotator = runtime_state.rotator
                    if rotator:
                        account = runtime_state.account_service.get_active_account() if runtime_state.account_service else None
                        if account:
                            rotator.record_error(account.id)
                    raise _upstream_exception(exc) from exc
                except AistudioError as exc:
                    _cleanup_persisted_image_items(image_store, items)
                    runtime_state.record(image_plan.model, "errors")
                    rotator = runtime_state.rotator
                    if rotator:
                        account = runtime_state.account_service.get_active_account() if runtime_state.account_service else None
                        if account:
                            rotator.record_error(account.id)
                    raise _upstream_exception(exc) from exc
                except Exception as exc:
                    _cleanup_persisted_image_items(image_store, items)
                    runtime_state.record(image_plan.model, "errors")
                    logger.error("Image error: %s", exc, exc_info=True)
                    raise HTTPException(500, detail={"message": str(exc), "type": "server_error"}) from exc

        # 所有重试都失败
        raise HTTPException(429, detail={"message": str(last_error), "type": "rate_limit_exceeded"}) from last_error
    finally:
        cleanup_files(image_paths)


def _cleanup_persisted_image_items(image_store: GeneratedImageStore, items: list[dict[str, Any]]) -> None:
    for item in items:
        path = item.get("path")
        if not path:
            continue
        try:
            image_store.delete(path)
        except OSError:
            logger.warning("Failed to clean up generated image after request failure")
        except ValueError:
            logger.warning("Skipped invalid generated image cleanup path after request failure")


def _build_streaming_response(
    *,
    client: AIStudioClient,
    capture_prompt: str,
    model: str,
    capture_images: list[str] | None,
    contents: list[AistudioContent],
    system_instruction: str | None,
    cleanup_paths: list[str],
    include_usage: bool = False,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    max_tokens: int | None = None,
    tools: list[list] | None = None,
    generation_config_overrides: dict | None = None,
    safety_off: bool = False,
    enable_thinking: bool = True,
    sanitize_plain_text: bool = True,
    request: Request | None = None,
) -> StreamingResponse:
    async def stream_response():
        busy_lock = runtime_state.busy_lock
        if busy_lock is None:
            yield sse_error("Server not ready")
            cleanup_files(cleanup_paths)
            return

        async with busy_lock:
            try:
                chat_id = new_chat_id()
                final_usage = None
                saw_tool_calls = False
                for stream_attempt in range(2):
                    if await _request_disconnected(request):
                        logger.info("OpenAI stream disconnected before downstream call")
                        return
                    upstream = None
                    try:
                        try:
                            upstream = client.stream_generate_content(
                                model=model,
                                capture_prompt=capture_prompt,
                                capture_images=capture_images,
                                contents=contents,
                                system_instruction_content=(
                                    AistudioContent(role="user", parts=[AistudioPart(text=system_instruction)])
                                    if system_instruction
                                    else None
                                ),
                                temperature=temperature,
                                top_p=top_p,
                                top_k=top_k,
                                max_tokens=max_tokens,
                                tools=tools,
                                generation_config_overrides=generation_config_overrides,
                                sanitize_plain_text=sanitize_plain_text,
                                safety_off=safety_off,
                                enable_thinking=enable_thinking,
                                force_refresh_capture=stream_attempt > 0,
                            )
                            async for event_type, text in upstream:
                                if await _request_disconnected(request):
                                    logger.info("OpenAI stream disconnected during downstream replay")
                                    return
                                if event_type == "body" and text:
                                    yield sse_chunk(chat_id, model, text, include_usage=include_usage)
                                elif event_type == "thinking" and text:
                                    yield sse_chunk(chat_id, model, "", thinking=text, include_usage=include_usage)
                                elif event_type == "tool_calls" and text:
                                    saw_tool_calls = True
                                    yield sse_chunk(
                                        chat_id,
                                        model,
                                        "",
                                        tool_calls=to_openai_tool_calls(text if isinstance(text, list) else []),
                                        include_usage=include_usage,
                                    )
                                elif event_type == "usage":
                                    final_usage = text if isinstance(text, dict) else None
                            break
                        finally:
                            if upstream is not None:
                                await _close_async_iterator(upstream)
                    except RequestError as exc:
                        if exc.status == 204 and stream_attempt == 0:
                            logger.warning("Stream 收到 204，清理 snapshot 缓存后重试一次")
                            client.clear_snapshot_cache()
                            continue
                        raise
                    except AuthError as exc:
                        if stream_attempt == 0:
                            logger.warning("Stream 鉴权异常，清理 snapshot 缓存后重试一次: %s", exc)
                            client.clear_snapshot_cache()
                            continue
                        raise

                runtime_state.record(model, "success", final_usage)
                yield sse_chunk(chat_id, model, "", finish="tool_calls" if saw_tool_calls else "stop", include_usage=include_usage)
                if include_usage:
                    yield sse_usage_chunk(chat_id, model, final_usage)
                yield "data: [DONE]\n\n"
            except asyncio.CancelledError:
                logger.info("OpenAI stream cancelled by client")
                raise
            except Exception as exc:
                runtime_state.record(model, "errors")
                message, error_type, code = _openai_stream_error_detail(exc)
                if error_type == "unsupported_feature":
                    logger.warning("OpenAI stream unsupported: %s", message)
                else:
                    logger.error("Stream error: %s", exc, exc_info=True)
                yield sse_error(message, error_type=error_type, code=code)
                yield "data: [DONE]\n\n"
            finally:
                cleanup_files(cleanup_paths)

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def handle_gemini_generate_content(
    model_path: str,
    req: GeminiGenerateContentRequest,
    client: AIStudioClient,
    *,
    stream: bool,
    request: Request | None = None,
):
    busy_lock = runtime_state.busy_lock
    if busy_lock is None:
        raise HTTPException(503, detail={"message": "Server not ready", "type": "service_unavailable"})
    if busy_lock.locked():
        raise HTTPException(429, detail={"message": "Server is busy", "type": "rate_limit_exceeded"})
    if stream and _client_is_pure_http(client):
        raise _unsupported(_pure_http_streaming_message())

    max_retries = 3
    last_error = None

    for attempt in range(max_retries):
        async with busy_lock:
            normalized = None
            try:
                normalized = normalize_gemini_request(req, model_path, stream=stream)
                if attempt == 0:
                    await _ensure_account_for_model(normalized["model"])
                logger.info(
                    "Gemini: model=%s, contents=%s, stream=%s, attempt=%d",
                    normalized["model"],
                    len(req.contents),
                    stream,
                    attempt + 1,
                )

                if stream:
                    return _build_gemini_streaming_response(client=client, normalized=normalized, request=request)

                output = await client.generate_content(
                    model=normalized["model"],
                    capture_prompt=normalized["capture_prompt"],
                    capture_images=normalized["capture_images"],
                    contents=normalized["contents"],
                    system_instruction_content=normalized["system_instruction"],
                    tools=normalized["tools"],
                    temperature=normalized["temperature"],
                    top_p=normalized["top_p"],
                    top_k=normalized["top_k"],
                    max_tokens=normalized["max_tokens"],
                    generation_config_overrides=normalized["generation_config_overrides"],
                    sanitize_plain_text=False,
                )

                # 记录成功
                rotator = runtime_state.rotator
                if rotator:
                    account = runtime_state.account_service.get_active_account() if runtime_state.account_service else None
                    if account:
                        rotator.record_success(account.id)

                runtime_state.record(normalized["model"], "success", output.usage)
                return {
                    "candidates": [
                        {
                            "content": {
                                "role": "model",
                                "parts": to_gemini_parts(
                                    output.text,
                                    function_calls=output.function_calls,
                                    function_responses=output.function_responses,
                                    thinking=output.thinking,
                                ),
                            },
                            "finishReason": "STOP" if not output.function_calls else "FUNCTION_CALL",
                        }
                    ],
                    "usageMetadata": to_gemini_usage_metadata(output.usage),
                }
            except ValueError as exc:
                raise HTTPException(400, detail={"message": str(exc), "type": "bad_request"}) from exc
            except UsageLimitExceeded as exc:
                runtime_state.record(model_path, "rate_limited")
                last_error = exc

                # 记录限流
                rotator = runtime_state.rotator
                if rotator:
                    account = runtime_state.account_service.get_active_account() if runtime_state.account_service else None
                    if account:
                        rotator.record_rate_limited(account.id)

                # 尝试切换账号
                if await _try_switch_account(normalized["model"] if normalized else model_path):
                    logger.info("Gemini 429 限流，已切换账号，重试 %d/%d", attempt + 1, max_retries)
                    continue
                else:
                    logger.warning("Gemini 429 限流，无法切换账号")
                    raise HTTPException(429, detail={"message": str(exc), "type": "rate_limit_exceeded"}) from exc
            except (AuthError, RequestError) as exc:
                runtime_state.record(model_path, "errors")
                rotator = runtime_state.rotator
                if rotator:
                    account = runtime_state.account_service.get_active_account() if runtime_state.account_service else None
                    if account:
                        rotator.record_error(account.id)
                raise _upstream_exception(exc) from exc
            except AistudioError as exc:
                runtime_state.record(model_path, "errors")
                rotator = runtime_state.rotator
                if rotator:
                    account = runtime_state.account_service.get_active_account() if runtime_state.account_service else None
                    if account:
                        rotator.record_error(account.id)
                raise _upstream_exception(exc) from exc
            except Exception as exc:
                runtime_state.record(model_path, "errors")
                logger.error("Gemini error: %s", exc, exc_info=True)
                raise HTTPException(500, detail={"message": str(exc), "type": "server_error"}) from exc
            finally:
                if normalized is not None and not stream:
                    cleanup_files(normalized["cleanup_paths"])

    raise HTTPException(429, detail={"message": str(last_error), "type": "rate_limit_exceeded"}) from last_error


def _build_gemini_streaming_response(*, client: AIStudioClient, normalized: dict, request: Request | None = None) -> StreamingResponse:
    async def stream_response():
        busy_lock = runtime_state.busy_lock
        if busy_lock is None:
            yield "data: " + json.dumps({"error": {"message": "Server not ready"}}, ensure_ascii=False) + "\n\n"
            cleanup_files(normalized["cleanup_paths"])
            return

        async with busy_lock:
            try:
                final_usage = None
                saw_tool_calls = False
                for stream_attempt in range(2):
                    if await _request_disconnected(request):
                        logger.info("Gemini stream disconnected before downstream call")
                        return
                    upstream = None
                    try:
                        try:
                            upstream = client.stream_generate_content(
                                model=normalized["model"],
                                capture_prompt=normalized["capture_prompt"],
                                capture_images=normalized["capture_images"],
                                contents=normalized["contents"],
                                system_instruction_content=normalized["system_instruction"],
                                tools=normalized["tools"],
                                temperature=normalized["temperature"],
                                top_p=normalized["top_p"],
                                top_k=normalized["top_k"],
                                max_tokens=normalized["max_tokens"],
                                generation_config_overrides=normalized["generation_config_overrides"],
                                sanitize_plain_text=False,
                                force_refresh_capture=stream_attempt > 0,
                            )
                            async for event_type, text in upstream:
                                if await _request_disconnected(request):
                                    logger.info("Gemini stream disconnected during downstream replay")
                                    return
                                if event_type == "body" and text:
                                    yield "data: " + json.dumps(
                                        {
                                            "candidates": [
                                                {
                                                    "content": {"role": "model", "parts": [{"text": text}]},
                                                    "finishReason": None,
                                                }
                                            ]
                                        },
                                        ensure_ascii=False,
                                    ) + "\n\n"
                                elif event_type == "thinking" and text:
                                    yield "data: " + json.dumps(
                                        {
                                            "candidates": [
                                                {
                                                    "content": {
                                                        "role": "model",
                                                        "parts": [{"text": text, "thought": True}],
                                                    },
                                                    "finishReason": None,
                                                }
                                            ]
                                        },
                                        ensure_ascii=False,
                                    ) + "\n\n"
                                elif event_type == "tool_calls" and text:
                                    saw_tool_calls = True
                                    yield "data: " + json.dumps(
                                        {
                                            "candidates": [
                                                {
                                                    "content": {
                                                        "role": "model",
                                                        "parts": to_gemini_parts(
                                                            "",
                                                            function_calls=text if isinstance(text, list) else [],
                                                        ),
                                                    },
                                                    "finishReason": None,
                                                }
                                            ]
                                        },
                                        ensure_ascii=False,
                                    ) + "\n\n"
                                elif event_type == "usage":
                                    final_usage = text if isinstance(text, dict) else None
                            break
                        finally:
                            if upstream is not None:
                                await _close_async_iterator(upstream)
                    except RequestError as exc:
                        if exc.status == 204 and stream_attempt == 0:
                            logger.warning("Gemini stream 收到 204，清理 snapshot 缓存后重试一次")
                            client.clear_snapshot_cache()
                            continue
                        raise
                    except AuthError as exc:
                        if stream_attempt == 0:
                            logger.warning("Gemini stream 鉴权异常，清理 snapshot 缓存后重试一次: %s", exc)
                            client.clear_snapshot_cache()
                            continue
                        raise

                runtime_state.record(normalized["model"], "success", final_usage)
                finish_payload: dict[str, Any] = {
                    "candidates": [{"finishReason": "FUNCTION_CALL" if saw_tool_calls else "STOP"}]
                }
                if final_usage:
                    finish_payload["usageMetadata"] = to_gemini_usage_metadata(final_usage)
                yield "data: " + json.dumps(finish_payload, ensure_ascii=False) + "\n\n"
                yield "data: [DONE]\n\n"
            except asyncio.CancelledError:
                logger.info("Gemini stream cancelled by client")
                raise
            except Exception as exc:
                runtime_state.record(normalized["model"], "errors")
                error_payload = _gemini_stream_error_payload(exc)
                if error_payload.get("error", {}).get("status") == "UNIMPLEMENTED":
                    logger.warning("Gemini stream unsupported: %s", error_payload["error"].get("message"))
                else:
                    logger.error("Gemini stream error: %s", exc, exc_info=True)
                yield "data: " + json.dumps(error_payload, ensure_ascii=False) + "\n\n"
                yield "data: [DONE]\n\n"
            finally:
                cleanup_files(normalized["cleanup_paths"])

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
