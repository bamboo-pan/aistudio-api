"""Local OpenAI-compatible studio persistence and payload helpers."""

from __future__ import annotations

import base64
import json
import re
import time
import uuid
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse

from aistudio_api.config import settings


_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_DATA_URI_RE = re.compile(r"^data:([^;,]+)?(;base64)?,(.*)$", re.DOTALL)
_HEAVY_FIELDS = {"data", "data_url", "file_data", "b64", "b64_json"}
_IMAGE_MODEL_PREFIXES = ("gpt-image-",)
_NON_CHAT_MODEL_MARKERS = ("audio", "realtime", "tts", "transcribe", "embedding")
GPT_IMAGE_2_SIZE_OPTIONS = [
    {"label": "Square", "size": "1024x1024", "note": "general-purpose default"},
    {"label": "HD portrait", "size": "1024x1536", "note": "standard portrait"},
    {"label": "HD landscape", "size": "1536x1024", "note": "standard landscape"},
    {"label": "Deck landscape", "size": "1536x864", "note": "16:9 slide or UI mock"},
    {"label": "2K / QHD", "size": "2560x1440", "note": "upper reliability boundary"},
    {"label": "Near 4K / UHD", "size": "3824x2144", "note": "experimental, below 3840px max edge"},
]
_GPT_IMAGE_2_SIZE_RE = re.compile(r"^(\d{2,5})x(\d{2,5})$")
_GPT_IMAGE_2_MAX_EDGE_EXCLUSIVE = 3840
_GPT_IMAGE_2_MAX_PIXELS = 8_294_400
_GPT_IMAGE_2_MIN_PIXELS = 655_360
_GPT_IMAGE_2_MAX_RATIO = 3

_MIME_EXTENSIONS = {
    "application/json": ".json",
    "application/pdf": ".pdf",
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "text/csv": ".csv",
    "text/markdown": ".md",
    "text/plain": ".txt",
}


def normalize_openai_base_url(value: str) -> str:
    base_url = str(value or "").strip().rstrip("/")
    if not base_url:
        raise ValueError("OpenAI-compatible base URL is required")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("OpenAI-compatible base URL must start with http:// or https://")
    return base_url


def upstream_url(base_url: str, path: str) -> str:
    return f"{normalize_openai_base_url(base_url)}/{path.lstrip('/')}"


def filter_chat_models(models: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for model in models:
        model_id = str(model.get("id") or model.get("name") or "").strip()
        if not model_id:
            continue
        lowered = model_id.lower()
        if any(lowered.startswith(prefix) for prefix in _IMAGE_MODEL_PREFIXES):
            continue
        if any(marker in lowered for marker in _NON_CHAT_MODEL_MARKERS):
            continue
        filtered.append(dict(model, id=model_id))
    return filtered


def validate_gpt_image_2_size(value: str) -> str:
    size = str(value or "").strip().lower()
    if not size:
        raise ValueError("gpt-image-2 size is required")
    if size == "auto":
        return size
    match = _GPT_IMAGE_2_SIZE_RE.fullmatch(size)
    if not match:
        raise ValueError("gpt-image-2 size must use WIDTHxHEIGHT format")
    width = int(match.group(1))
    height = int(match.group(2))
    if width % 16 or height % 16:
        raise ValueError("gpt-image-2 size edges must be multiples of 16")
    if max(width, height) >= _GPT_IMAGE_2_MAX_EDGE_EXCLUSIVE:
        raise ValueError("gpt-image-2 maximum edge must be less than 3840px")
    if max(width, height) / min(width, height) > _GPT_IMAGE_2_MAX_RATIO:
        raise ValueError("gpt-image-2 size ratio must not exceed 3:1")
    pixels = width * height
    if pixels > _GPT_IMAGE_2_MAX_PIXELS:
        raise ValueError("gpt-image-2 size total pixels must not exceed 8,294,400")
    if pixels < _GPT_IMAGE_2_MIN_PIXELS:
        raise ValueError("gpt-image-2 size total pixels must be at least 655,360")
    return f"{width}x{height}"


def build_image_generation_tool(options: Mapping[str, Any] | None) -> dict[str, Any] | None:
    options = options or {}
    if not options.get("image_tool_enabled"):
        return None
    tool: dict[str, Any] = {"type": "image_generation", "model": "gpt-image-2"}
    for key in ("size", "quality", "background", "output_format", "output_compression"):
        value = options.get(key)
        if value not in (None, ""):
            if key == "size":
                value = validate_gpt_image_2_size(str(value))
            tool[key] = value
    return tool


def build_images_generation_payload(prompt: str, options: Mapping[str, Any] | None) -> dict[str, Any]:
    text = str(prompt or "").strip()
    if not text:
        raise ValueError("image fallback prompt is required")
    options = options or {}
    payload: dict[str, Any] = {"model": "gpt-image-2", "prompt": text, "n": 1}
    size = options.get("size")
    if size not in (None, ""):
        payload["size"] = validate_gpt_image_2_size(str(size))
    for key in ("quality", "background", "output_format", "output_compression"):
        value = options.get(key)
        if value not in (None, "", "auto"):
            payload[key] = value
    return payload


def build_responses_payload(
    *,
    model: str,
    messages: list[Mapping[str, Any]],
    options: Mapping[str, Any] | None = None,
    asset_resolver: Callable[[Mapping[str, Any]], str] | None = None,
) -> dict[str, Any]:
    if not model:
        raise ValueError("model is required")
    options = options or {}
    payload: dict[str, Any] = {
        "model": model,
        "input": [_message_to_response_input(message, asset_resolver) for message in messages if message.get("role") in {"user", "assistant"}],
    }
    reasoning: dict[str, Any] = {}
    effort = str(options.get("reasoning_effort") or "off").strip()
    summary = str(options.get("reasoning_summary") or "").strip()
    if effort and effort != "off":
        reasoning["effort"] = effort
    if summary and summary != "none":
        reasoning["summary"] = summary
    if reasoning:
        payload["reasoning"] = reasoning
    tool = build_image_generation_tool(options)
    if tool:
        payload["tools"] = [tool]
    return payload


def parse_responses_output(payload: Mapping[str, Any]) -> dict[str, Any]:
    text_parts: list[str] = []
    thinking_parts: list[str] = []
    image_candidates: list[dict[str, Any]] = []

    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text:
        text_parts.append(output_text)

    explicit_thinking = payload.get("thinking")
    if isinstance(explicit_thinking, str) and explicit_thinking:
        thinking_parts.append(explicit_thinking)

    for item in payload.get("output") if isinstance(payload.get("output"), list) else []:
        if not isinstance(item, Mapping):
            continue
        item_type = str(item.get("type") or "")
        if item_type == "reasoning":
            thinking_parts.extend(_text_from_parts(item.get("summary")))
            thinking_parts.extend(_text_from_parts(item.get("content")))
        elif item_type in {"message", "output_text"}:
            text_parts.extend(_text_from_parts(item.get("content")))
            if isinstance(item.get("text"), str):
                text_parts.append(str(item["text"]))
        elif item_type == "image_generation_call":
            image_candidates.extend(_image_candidates_from_mapping(item))
        else:
            text_parts.extend(_text_from_parts(item.get("content")))
            image_candidates.extend(_image_candidates_from_mapping(item))

    image_candidates.extend(_image_candidates_from_mapping(payload))
    return {
        "content": "".join(text_parts).strip(),
        "thinking": "\n".join(part for part in thinking_parts if part).strip(),
        "usage": payload.get("usage") if isinstance(payload.get("usage"), Mapping) else None,
        "image_candidates": image_candidates,
    }


class LocalStudioStore:
    """Persist local OpenAI studio conversations and uploaded/generated assets."""

    def __init__(self, storage_dir: str | Path | None = None, *, max_conversations: int = 300) -> None:
        self.root = Path(storage_dir or settings.local_studio_dir).expanduser().resolve()
        self.conversations_dir = self.root / "conversations"
        self.files_dir = self.root / "files"
        self.max_conversations = max_conversations

    def ensure_directory(self) -> None:
        self.conversations_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[dict[str, Any]]:
        self.ensure_directory()
        conversations: list[dict[str, Any]] = []
        for path in self.conversations_dir.glob("*.json"):
            try:
                conversations.append(self._summary(self._read_json(path)))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        conversations.sort(key=lambda item: item.get("updated_at") or item.get("created_at") or 0, reverse=True)
        return conversations[: self.max_conversations]

    def create(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        now = int(time.time())
        conversation = {
            "id": uuid.uuid4().hex,
            "title": str(payload.get("title") or "New conversation")[:80],
            "created_at": now,
            "updated_at": now,
            "model": str(payload.get("model") or ""),
            "settings": dict(payload.get("settings") or {}),
            "messages": [],
        }
        return self.save(conversation)

    def get(self, conversation_id: str) -> dict[str, Any]:
        path = self._path_for(conversation_id)
        if not path.is_file():
            raise FileNotFoundError(conversation_id)
        return self._read_json(path)

    def save(self, conversation: Mapping[str, Any]) -> dict[str, Any]:
        data = self._strip_heavy_fields(dict(conversation))
        conversation_id = self._validate_id(str(data.get("id") or uuid.uuid4().hex))
        now = int(time.time())
        existing = self._read_json(self._path_for(conversation_id)) if self._path_for(conversation_id).is_file() else {}
        data["id"] = conversation_id
        data["created_at"] = int(data.get("created_at") or existing.get("created_at") or now)
        data["updated_at"] = now
        data["messages"] = [self._normalize_message(message) for message in data.get("messages") if isinstance(message, Mapping)] if isinstance(data.get("messages"), list) else []
        data["title"] = self._title_for(data)
        self.ensure_directory()
        self._write_json(self._path_for(conversation_id), data)
        self._prune_old_conversations()
        return data

    def patch(self, conversation_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        conversation = self.get(conversation_id)
        if "title" in payload:
            conversation["title"] = str(payload.get("title") or "").strip()[:80] or self._title_for(conversation)
        if "model" in payload:
            conversation["model"] = str(payload.get("model") or "")
        if isinstance(payload.get("settings"), Mapping):
            conversation["settings"] = dict(payload["settings"])
        return self.save(conversation)

    def delete(self, conversation_id: str) -> bool:
        path = self._path_for(conversation_id)
        if not path.is_file():
            return False
        path.unlink()
        return True

    def bulk_delete(self, conversation_ids: Iterable[str]) -> dict[str, Any]:
        deleted: list[str] = []
        missing: list[str] = []
        seen: set[str] = set()
        for raw_id in conversation_ids:
            conversation_id = str(raw_id or "").strip()
            if not conversation_id or conversation_id in seen:
                continue
            seen.add(conversation_id)
            if self.delete(conversation_id):
                deleted.append(conversation_id)
            else:
                missing.append(conversation_id)
        return {"deleted": deleted, "missing": missing, "deleted_count": len(deleted)}

    def add_user_message(self, conversation: dict[str, Any], content: str, files: list[Mapping[str, Any]]) -> dict[str, Any]:
        now = int(time.time())
        attachments = [self.save_data_url_asset(file) for file in files]
        message = {
            "id": uuid.uuid4().hex,
            "role": "user",
            "content": str(content or ""),
            "attachments": attachments,
            "created_at": now,
        }
        conversation.setdefault("messages", []).append(message)
        return message

    def add_assistant_message(
        self,
        conversation: dict[str, Any],
        *,
        content: str = "",
        thinking: str = "",
        usage: Mapping[str, Any] | None = None,
        images: list[Mapping[str, Any]] | None = None,
        error: str = "",
    ) -> dict[str, Any]:
        message = {
            "id": uuid.uuid4().hex,
            "role": "assistant",
            "content": content,
            "thinking": thinking,
            "usage": dict(usage or {}),
            "images": [dict(image) for image in images or []],
            "error": error,
            "created_at": int(time.time()),
        }
        conversation.setdefault("messages", []).append(message)
        return message

    def truncate_for_rerun(self, conversation: dict[str, Any], message_index: int) -> dict[str, Any]:
        messages = conversation.get("messages") if isinstance(conversation.get("messages"), list) else []
        user_index = -1
        for index in range(min(message_index, len(messages) - 1), -1, -1):
            if isinstance(messages[index], Mapping) and messages[index].get("role") == "user":
                user_index = index
                break
        if user_index < 0:
            raise ValueError("No user message is available to rerun")
        conversation["messages"] = messages[: user_index + 1]
        return conversation["messages"][user_index]

    def save_data_url_asset(self, file: Mapping[str, Any]) -> dict[str, Any]:
        data_url = str(file.get("data_url") or file.get("url") or file.get("file_data") or "")
        data, mime_type = decode_data_uri(data_url, fallback_mime=str(file.get("mime") or file.get("mime_type") or "application/octet-stream"))
        return self.save_binary_asset(
            data,
            mime_type,
            filename=str(file.get("name") or file.get("filename") or "upload"),
            source=str(file.get("source") or "upload"),
        )

    def save_binary_asset(self, data: bytes, mime_type: str, *, filename: str = "asset", source: str = "generated") -> dict[str, Any]:
        self.ensure_directory()
        created = int(time.time())
        day = datetime.fromtimestamp(created, UTC).strftime("%Y%m%d")
        asset_id = uuid.uuid4().hex
        extension = _extension_for_mime(mime_type, filename)
        relative_path = Path(day) / f"{asset_id}{extension}"
        target = self.files_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        path = relative_path.as_posix()
        return {
            "id": asset_id,
            "name": filename[:160] or f"asset{extension}",
            "mime": mime_type or "application/octet-stream",
            "size": len(data),
            "path": path,
            "url": self.public_url(path),
            "source": source,
            "created_at": created,
        }

    def save_response_images(self, candidates: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        images: list[dict[str, Any]] = []
        for index, candidate in enumerate(candidates, start=1):
            try:
                if candidate.get("data_url"):
                    data, mime_type = decode_data_uri(str(candidate["data_url"]), fallback_mime=str(candidate.get("mime") or "image/png"))
                    saved = self.save_binary_asset(data, mime_type, filename=f"generated-{index}", source="generated")
                elif candidate.get("b64_json") or candidate.get("b64") or candidate.get("result"):
                    encoded = str(candidate.get("b64_json") or candidate.get("b64") or candidate.get("result") or "")
                    data = base64.b64decode(encoded)
                    saved = self.save_binary_asset(data, str(candidate.get("mime") or "image/png"), filename=f"generated-{index}", source="generated")
                elif candidate.get("url"):
                    saved = {"id": uuid.uuid4().hex, "url": str(candidate["url"]), "name": f"generated-{index}", "mime": str(candidate.get("mime") or "image/png"), "source": "generated"}
                else:
                    continue
            except (ValueError, OSError):
                continue
            images.append(saved)
        return images

    def asset_to_data_url(self, asset: Mapping[str, Any]) -> str:
        path = self.resolve_asset_path(str(asset.get("path") or ""))
        data = path.read_bytes()
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{asset.get('mime') or 'application/octet-stream'};base64,{encoded}"

    def public_url(self, relative_path: str) -> str:
        encoded = "/".join(quote(part) for part in relative_path.replace("\\", "/").split("/") if part)
        return f"/api/local-studio/assets/{encoded}"

    def resolve_asset_path(self, asset_path_or_url: str) -> Path:
        raw = str(asset_path_or_url or "").strip()
        if not raw or "\x00" in raw:
            raise ValueError("asset path is required")
        parsed = urlparse(raw)
        path = parsed.path if parsed.scheme or parsed.netloc else raw
        path = unquote(path).replace("\\", "/")
        prefix = "/api/local-studio/assets/"
        if path.startswith(prefix):
            path = path[len(prefix) :]
        elif path.startswith("/"):
            raise ValueError("asset path is outside local studio storage")
        candidate = (self.files_dir / path).resolve()
        try:
            candidate.relative_to(self.files_dir)
        except ValueError as exc:
            raise ValueError("asset path is outside local studio storage") from exc
        if candidate == self.files_dir or not candidate.is_file():
            raise FileNotFoundError(path)
        return candidate

    def _path_for(self, conversation_id: str) -> Path:
        return self.conversations_dir / f"{self._validate_id(conversation_id)}.json"

    def _validate_id(self, value: str) -> str:
        conversation_id = str(value or "").strip()
        if not _ID_RE.fullmatch(conversation_id):
            raise ValueError("conversation id is invalid")
        return conversation_id

    def _read_json(self, path: Path) -> dict[str, Any]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("conversation file must contain an object")
        return data

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        tmp_path.replace(path)

    def _normalize_message(self, message: Mapping[str, Any]) -> dict[str, Any]:
        role = "assistant" if message.get("role") == "assistant" else "user"
        normalized = {
            "id": str(message.get("id") or uuid.uuid4().hex),
            "role": role,
            "content": str(message.get("content") or ""),
            "created_at": int(message.get("created_at") or time.time()),
        }
        for key in ("thinking", "error"):
            if message.get(key):
                normalized[key] = str(message[key])
        if isinstance(message.get("usage"), Mapping):
            normalized["usage"] = dict(message["usage"])
        for key in ("attachments", "images"):
            if isinstance(message.get(key), list):
                normalized[key] = [self._strip_heavy_fields(dict(item)) for item in message[key] if isinstance(item, Mapping)]
        return normalized

    def _summary(self, conversation: Mapping[str, Any]) -> dict[str, Any]:
        messages = conversation.get("messages") if isinstance(conversation.get("messages"), list) else []
        last_message = next((message for message in reversed(messages) if isinstance(message, Mapping)), {})
        return {
            "id": conversation.get("id", ""),
            "title": self._title_for(conversation),
            "created_at": conversation.get("created_at"),
            "updated_at": conversation.get("updated_at"),
            "model": conversation.get("model", ""),
            "message_count": len(messages),
            "preview": str(last_message.get("error") or last_message.get("content") or "")[:120],
            "last_error": str(last_message.get("error") or ""),
        }

    def _title_for(self, conversation: Mapping[str, Any]) -> str:
        title = str(conversation.get("title") or "").strip()
        if title and title != "New conversation":
            return title[:80]
        messages = conversation.get("messages") if isinstance(conversation.get("messages"), list) else []
        for message in messages:
            if isinstance(message, Mapping) and message.get("role") == "user":
                content = str(message.get("content") or "").strip()
                if content:
                    return content[:80]
                attachments = message.get("attachments") if isinstance(message.get("attachments"), list) else []
                if attachments:
                    return "Attachment conversation"
        return title[:80] or "New conversation"

    def _strip_heavy_fields(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._strip_heavy_fields(item) for item in value]
        if isinstance(value, dict):
            return {str(key): self._strip_heavy_fields(item) for key, item in value.items() if str(key) not in _HEAVY_FIELDS}
        return value

    def _prune_old_conversations(self) -> None:
        files = []
        for path in self.conversations_dir.glob("*.json"):
            try:
                data = self._read_json(path)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            files.append((data.get("updated_at") or data.get("created_at") or 0, path.name, path))
        files.sort(reverse=True)
        for _, _, path in files[self.max_conversations :]:
            try:
                path.unlink()
            except FileNotFoundError:
                continue


def decode_data_uri(value: str, *, fallback_mime: str = "application/octet-stream") -> tuple[bytes, str]:
    match = _DATA_URI_RE.match(value or "")
    if not match:
        raise ValueError("file data must be a data URL")
    mime_type = match.group(1) or fallback_mime
    payload = match.group(3) or ""
    if match.group(2):
        return base64.b64decode(payload), mime_type
    return unquote(payload).encode("utf-8"), mime_type


def _extension_for_mime(mime_type: str | None, filename: str = "") -> str:
    normalized = (mime_type or "").split(";", 1)[0].strip().lower()
    if normalized in _MIME_EXTENSIONS:
        return _MIME_EXTENSIONS[normalized]
    suffix = Path(filename or "").suffix.lower()
    return suffix if suffix and len(suffix) <= 8 else ".bin"


def _message_to_response_input(message: Mapping[str, Any], asset_resolver: Callable[[Mapping[str, Any]], str] | None) -> dict[str, Any]:
    role = "assistant" if message.get("role") == "assistant" else "user"
    content = str(message.get("content") or "")
    if role == "assistant":
        return {"role": "assistant", "content": content}
    blocks: list[dict[str, Any]] = []
    if content:
        blocks.append({"type": "input_text", "text": content})
    attachments = message.get("attachments") if isinstance(message.get("attachments"), list) else []
    for attachment in attachments:
        if not isinstance(attachment, Mapping):
            continue
        data_url = str(attachment.get("data_url") or attachment.get("file_data") or "")
        if not data_url and asset_resolver is not None:
            data_url = asset_resolver(attachment)
        if not data_url:
            continue
        mime_type = str(attachment.get("mime") or attachment.get("mime_type") or "application/octet-stream")
        if mime_type.startswith("image/"):
            blocks.append({"type": "input_image", "image_url": data_url})
        else:
            blocks.append({"type": "input_file", "filename": str(attachment.get("name") or "upload"), "file_data": data_url})
    return {"role": "user", "content": blocks or content}


def _text_from_parts(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, Mapping):
                for key in ("text", "output_text", "reasoning_text", "summary_text"):
                    text = item.get(key)
                    if isinstance(text, str) and text:
                        parts.append(text)
        return parts
    if isinstance(value, Mapping):
        return _text_from_parts([value])
    return []


def _image_candidates_from_mapping(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for key in ("b64_json", "b64", "result"):
        item = value.get(key)
        if isinstance(item, str) and item:
            candidates.append({key: item, "mime": value.get("mime") or value.get("mime_type") or "image/png"})
    url = value.get("url")
    if isinstance(url, str) and url:
        if url.startswith("data:image/"):
            candidates.append({"data_url": url, "mime": value.get("mime") or value.get("mime_type") or "image/png"})
        else:
            candidates.append({"url": url, "mime": value.get("mime") or value.get("mime_type") or "image/png"})
    for key in ("data", "content"):
        item = value.get(key)
        if isinstance(item, list):
            for part in item:
                if isinstance(part, Mapping):
                    candidates.extend(_image_candidates_from_mapping(part))
    return candidates
