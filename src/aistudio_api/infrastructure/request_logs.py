"""Outbound AI Studio request log persistence helpers."""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from collections.abc import Mapping
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aistudio_api.config import settings


_REQUEST_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_CURRENT_CHAIN_ID: ContextVar[str | None] = ContextVar("aistudio_request_log_chain_id", default=None)


def new_request_chain_id() -> str:
    return uuid.uuid4().hex


def current_request_chain_id() -> str | None:
    return _CURRENT_CHAIN_ID.get()


def set_request_chain_id(chain_id: str) -> Token[str | None]:
    return _CURRENT_CHAIN_ID.set(str(chain_id or ""))


def reset_request_chain_id(token: Token[str | None]) -> None:
    _CURRENT_CHAIN_ID.reset(token)


class RequestLogStore:
    """Store complete outbound AI Studio requests as JSON files."""

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        self.root = Path(storage_dir or settings.request_logs_dir).expanduser().resolve()
        self.entries_dir = self.root / "entries"
        self.state_path = self.root / "state.json"
        self._lock = threading.RLock()

    def ensure_directory(self) -> None:
        self.entries_dir.mkdir(parents=True, exist_ok=True)

    def status(self) -> dict[str, Any]:
        return {"enabled": self.is_enabled(), "count": self.count()}

    def is_enabled(self) -> bool:
        return bool(self._read_state().get("enabled", False))

    def set_enabled(self, enabled: bool) -> dict[str, Any]:
        with self._lock:
            self.ensure_directory()
            state = {"enabled": bool(enabled), "updated_at": self._now_iso()}
            self._write_json(self.state_path, state)
            return self.status()

    def count(self) -> int:
        self.ensure_directory()
        return sum(1 for path in self.entries_dir.glob("*.json") if path.is_file())

    def list(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        self.ensure_directory()
        items = []
        for path in self.entries_dir.glob("*.json"):
            try:
                items.append(self._summary(self._read_entry(path)))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        items.sort(key=lambda item: (item.get("created_at_unix") or 0, item.get("id") or ""), reverse=True)
        if limit is not None:
            return items[: max(0, limit)]
        return items

    def get(self, request_id: str) -> dict[str, Any]:
        path = self._path_for(request_id)
        if not path.is_file():
            raise FileNotFoundError(request_id)
        return self._read_entry(path)

    def save(
        self,
        *,
        kind: str,
        model: str | None,
        method: str,
        url: str,
        headers: Mapping[str, Any],
        body: str | bytes,
        captured_headers: Mapping[str, Any] | None = None,
        transport: str = "",
        chain_id: str | None = None,
        direction: str = "outbound",
        phase: str | None = None,
        status_code: int | None = None,
        response_headers: Mapping[str, Any] | None = None,
        response_body: str | bytes | None = None,
        elapsed_ms: float | None = None,
    ) -> dict[str, Any] | None:
        if not self.is_enabled():
            return None

        request_id = uuid.uuid4().hex
        body_raw = self._body_to_text(body)
        body_json, body_parse_error = self._parse_body(body_raw)
        created_at_unix = time.time()
        response_fields = self._response_fields(response_headers=response_headers, response_body=response_body)
        entry = {
            "id": request_id,
            "chain_id": str(chain_id or current_request_chain_id() or request_id),
            "created_at": self._now_iso(created_at_unix),
            "created_at_unix": created_at_unix,
            "kind": str(kind or "request"),
            "model": str(model or ""),
            "transport": str(transport or ""),
            "direction": str(direction or "outbound"),
            "phase": str(phase or self._default_phase(direction)),
            "method": str(method or "POST").upper(),
            "url": str(url or ""),
            "headers": self._string_mapping(headers),
            "captured_headers": self._string_mapping(captured_headers or headers),
            "body_size": len(body_raw.encode("utf-8")),
            "body_raw": body_raw,
            "body_json": body_json,
            "body_parse_error": body_parse_error,
        }
        if status_code is not None:
            entry["status_code"] = int(status_code)
        if elapsed_ms is not None:
            entry["elapsed_ms"] = round(float(elapsed_ms), 3)
        entry.update(response_fields)
        with self._lock:
            self.ensure_directory()
            self._write_json(self._path_for(request_id), entry)
        return entry

    def attach_response(
        self,
        request_id: str,
        *,
        status_code: int | None = None,
        response_headers: Mapping[str, Any] | None = None,
        response_body: str | bytes | None = None,
        elapsed_ms: float | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            path = self._path_for(request_id)
            if not path.is_file():
                raise FileNotFoundError(request_id)
            entry = self._read_entry(path)
            if status_code is not None:
                entry["status_code"] = int(status_code)
            if elapsed_ms is not None:
                entry["elapsed_ms"] = round(float(elapsed_ms), 3)
            entry.update(self._response_fields(response_headers=response_headers, response_body=response_body))
            self._write_json(path, entry)
            return entry

    def _path_for(self, request_id: str) -> Path:
        value = str(request_id or "").strip()
        if not _REQUEST_ID_RE.fullmatch(value):
            raise ValueError("request log id is invalid")
        return self.entries_dir / f"{value}.json"

    def _read_state(self) -> dict[str, Any]:
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {"enabled": False}
        return data if isinstance(data, dict) else {"enabled": False}

    def _read_entry(self, path: Path) -> dict[str, Any]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("request log file must contain an object")
        return data

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(path)

    def _summary(self, entry: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": entry.get("id", ""),
            "created_at": entry.get("created_at"),
            "created_at_unix": entry.get("created_at_unix"),
            "kind": entry.get("kind", ""),
            "model": entry.get("model", ""),
            "transport": entry.get("transport", ""),
            "chain_id": entry.get("chain_id", ""),
            "direction": entry.get("direction", ""),
            "phase": entry.get("phase", ""),
            "status_code": entry.get("status_code"),
            "elapsed_ms": entry.get("elapsed_ms"),
            "method": entry.get("method", "POST"),
            "url": entry.get("url", ""),
            "body_size": entry.get("body_size", 0),
            "response_body_size": entry.get("response_body_size", 0),
        }

    def _body_to_text(self, body: str | bytes) -> str:
        if isinstance(body, bytes):
            return body.decode("utf-8", errors="replace")
        return str(body)

    def _parse_body(self, body: str) -> tuple[Any, str | None]:
        if body == "":
            return None, None
        try:
            return json.loads(body), None
        except json.JSONDecodeError as exc:
            return None, str(exc)

    def _response_fields(
        self,
        *,
        response_headers: Mapping[str, Any] | None,
        response_body: str | bytes | None,
    ) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        if response_headers is not None:
            fields["response_headers"] = self._string_mapping(response_headers)
        if response_body is not None:
            response_body_raw = self._body_to_text(response_body)
            response_body_json, response_body_parse_error = self._parse_body(response_body_raw)
            fields.update(
                {
                    "response_body_size": len(response_body_raw.encode("utf-8")),
                    "response_body_raw": response_body_raw,
                    "response_body_json": response_body_json,
                    "response_body_parse_error": response_body_parse_error,
                }
            )
        return fields

    def _string_mapping(self, mapping: Mapping[str, Any]) -> dict[str, str]:
        return {str(key): str(value) for key, value in mapping.items()}

    def _default_phase(self, direction: str) -> str:
        return "upstream_request" if str(direction or "").lower() == "outbound" else "request"

    def _now_iso(self, value: float | None = None) -> str:
        return datetime.fromtimestamp(value or time.time(), UTC).isoformat().replace("+00:00", "Z")