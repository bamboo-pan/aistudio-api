"""OpenAI-compatible local studio routes."""

from __future__ import annotations

import time
from typing import Any

import httpx
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse

from aistudio_api.infrastructure.local_studio import (
    LocalStudioStore,
    build_images_generation_payload,
    build_responses_payload,
    filter_chat_models,
    normalize_openai_base_url,
    parse_responses_output,
    upstream_url,
)


router = APIRouter(prefix="/api/local-studio")


def _error_detail(message: str, error_type: str = "bad_request") -> dict[str, str]:
    return {"message": message, "type": error_type}


def _settings_from_payload(payload: dict[str, Any]) -> tuple[str, str, int]:
    try:
        base_url = normalize_openai_base_url(str(payload.get("base_url") or payload.get("apiUrl") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=_error_detail(str(exc), "invalid_request_error")) from exc
    token = str(payload.get("api_key") or payload.get("token") or "").strip()
    if "\n" in token or "\r" in token:
        raise HTTPException(status_code=400, detail=_error_detail("API token must be a single line", "invalid_request_error"))
    timeout = int(payload.get("timeout") or 120)
    timeout = max(1, min(timeout, 600))
    return base_url, token, timeout


def _auth_headers(token: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _new_http_client(timeout: int) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout)


def _upstream_error(exc: httpx.HTTPStatusError) -> HTTPException:
    response = exc.response
    message = response.text or response.reason_phrase or f"HTTP {response.status_code}"
    try:
        data = response.json()
        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, dict):
                message = str(error.get("message") or message)
            elif data.get("detail"):
                detail = data["detail"]
                message = str(detail.get("message") if isinstance(detail, dict) else detail)
    except ValueError:
        pass
    status = response.status_code if 400 <= response.status_code < 500 else 502
    return HTTPException(status_code=status, detail=_error_detail(f"HTTP {response.status_code}: {message}", "upstream_error"))


def _latest_user_prompt(conversation: dict[str, Any]) -> str:
    messages = conversation.get("messages") if isinstance(conversation.get("messages"), list) else []
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "user":
            text = str(message.get("content") or "").strip()
            if text:
                return text
    return ""


async def _call_images_generation_fallback(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    token: str,
    conversation: dict[str, Any],
    options: dict[str, Any],
) -> dict[str, Any] | None:
    if not options.get("image_tool_enabled"):
        return None
    prompt = _latest_user_prompt(conversation)
    if not prompt:
        return None
    payload = build_images_generation_payload(prompt, options)
    response = await client.post(upstream_url(base_url, "/images/generations"), headers=_auth_headers(token), json=payload)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else None


@router.get("/health")
async def health() -> dict[str, Any]:
    store = LocalStudioStore()
    store.ensure_directory()
    return {"ok": True, "storage": str(store.root)}


@router.post("/models")
async def list_models(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    base_url, token, timeout = _settings_from_payload(payload)
    try:
        async with _new_http_client(timeout) as client:
            response = await client.get(upstream_url(base_url, "/models"), headers=_auth_headers(token))
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise _upstream_error(exc) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail=_error_detail("Model list request timed out", "upstream_timeout")) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=_error_detail(str(exc), "upstream_error")) from exc

    data = response.json()
    models = data.get("data") if isinstance(data, dict) else []
    return {"object": "list", "data": filter_chat_models(models if isinstance(models, list) else [])}


@router.get("/conversations")
async def list_conversations() -> dict[str, Any]:
    return {"data": LocalStudioStore().list()}


@router.post("/conversations")
async def create_conversation(payload: dict[str, Any] | None = Body(None)) -> dict[str, Any]:
    try:
        return LocalStudioStore().create(payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=_error_detail(str(exc))) from exc


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str) -> dict[str, Any]:
    try:
        return LocalStudioStore().get(conversation_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=_error_detail("conversation not found", "not_found")) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=_error_detail(str(exc))) from exc


@router.patch("/conversations/{conversation_id}")
async def update_conversation(conversation_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return LocalStudioStore().patch(conversation_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=_error_detail("conversation not found", "not_found")) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=_error_detail(str(exc))) from exc


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str) -> dict[str, Any]:
    store = LocalStudioStore()
    try:
        deleted = store.delete(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=_error_detail(str(exc))) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail=_error_detail("conversation not found", "not_found"))
    return {"ok": True, "id": conversation_id}


@router.post("/conversations/bulk-delete")
async def bulk_delete_conversations(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    ids = payload.get("ids") if isinstance(payload, dict) else []
    if not isinstance(ids, list):
        raise HTTPException(status_code=400, detail=_error_detail("ids must be a list"))
    try:
        return LocalStudioStore().bulk_delete(ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=_error_detail(str(exc))) from exc


@router.get("/assets/{asset_path:path}")
async def get_asset(asset_path: str) -> FileResponse:
    store = LocalStudioStore()
    try:
        path = store.resolve_asset_path(asset_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=_error_detail("asset not found", "not_found")) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=_error_detail(str(exc))) from exc
    return FileResponse(path)


@router.post("/chat")
async def chat(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    store = LocalStudioStore()
    base_url, token, timeout = _settings_from_payload(payload)
    model = str(payload.get("model") or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail=_error_detail("model is required", "invalid_request_error"))

    conversation_id = str(payload.get("conversation_id") or "").strip()
    try:
        conversation = store.get(conversation_id) if conversation_id else store.create({"model": model, "settings": payload.get("options") or {}})
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=_error_detail("conversation not found", "not_found")) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=_error_detail(str(exc))) from exc

    rerun_index = payload.get("rerun_from")
    if rerun_index is not None:
        try:
            store.truncate_for_rerun(conversation, int(rerun_index))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=_error_detail(str(exc))) from exc
    else:
        content = str(payload.get("message") or "")
        files = payload.get("files") if isinstance(payload.get("files"), list) else []
        if not content.strip() and not files:
            raise HTTPException(status_code=400, detail=_error_detail("message or files are required", "invalid_request_error"))
        store.add_user_message(conversation, content, files)

    conversation["model"] = model
    if isinstance(payload.get("options"), dict):
        conversation["settings"] = dict(payload["options"])

    try:
        request_body = build_responses_payload(
            model=model,
            messages=conversation.get("messages", []),
            options=payload.get("options") if isinstance(payload.get("options"), dict) else {},
            asset_resolver=store.asset_to_data_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=_error_detail(str(exc), "invalid_request_error")) from exc

    started = time.perf_counter()
    options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    fallback_data: dict[str, Any] | None = None
    response_data: dict[str, Any] = {}
    try:
        async with _new_http_client(timeout) as client:
            try:
                response = await client.post(upstream_url(base_url, "/responses"), headers=_auth_headers(token), json=request_body)
                response.raise_for_status()
                raw_response_data = response.json()
                response_data = raw_response_data if isinstance(raw_response_data, dict) else {}
            except httpx.HTTPError:
                if not options.get("image_tool_enabled"):
                    raise
                fallback_data = await _call_images_generation_fallback(client=client, base_url=base_url, token=token, conversation=conversation, options=options)
                if fallback_data is None:
                    raise
    except httpx.HTTPStatusError as exc:
        error = _upstream_error(exc)
        store.add_assistant_message(conversation, error=error.detail["message"] if isinstance(error.detail, dict) else str(error.detail))
        store.save(conversation)
        raise error
    except httpx.TimeoutException as exc:
        message = f"HTTP 504: upstream request timed out after {timeout}s"
        store.add_assistant_message(conversation, error=message)
        store.save(conversation)
        raise HTTPException(status_code=504, detail=_error_detail(message, "upstream_timeout")) from exc
    except httpx.HTTPError as exc:
        message = str(exc)
        store.add_assistant_message(conversation, error=message)
        store.save(conversation)
        raise HTTPException(status_code=502, detail=_error_detail(message, "upstream_error")) from exc

    data = fallback_data if fallback_data is not None else response_data
    parsed = parse_responses_output(data if isinstance(data, dict) else {})
    images = store.save_response_images(parsed["image_candidates"])
    if not images and fallback_data is None and options.get("image_tool_enabled"):
        try:
            async with _new_http_client(timeout) as client:
                fallback_data = await _call_images_generation_fallback(client=client, base_url=base_url, token=token, conversation=conversation, options=options)
            if fallback_data:
                data = fallback_data
                parsed = parse_responses_output(fallback_data)
                images = store.save_response_images(parsed["image_candidates"])
        except httpx.HTTPStatusError as exc:
            error = _upstream_error(exc)
            store.add_assistant_message(conversation, error=error.detail["message"] if isinstance(error.detail, dict) else str(error.detail))
            store.save(conversation)
            raise error
        except httpx.TimeoutException as exc:
            message = f"HTTP 504: image fallback request timed out after {timeout}s"
            store.add_assistant_message(conversation, error=message)
            store.save(conversation)
            raise HTTPException(status_code=504, detail=_error_detail(message, "upstream_timeout")) from exc
        except httpx.HTTPError as exc:
            message = str(exc)
            store.add_assistant_message(conversation, error=message)
            store.save(conversation)
            raise HTTPException(status_code=502, detail=_error_detail(message, "upstream_error")) from exc
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    content = parsed["content"] or ("Generated image" if images else "")
    store.add_assistant_message(conversation, content=content or "(no response content)", thinking=parsed["thinking"], usage=parsed["usage"], images=images)
    saved = store.save(conversation)
    return {"conversation": saved, "request": request_body, "elapsed_ms": elapsed_ms, "upstream_id": data.get("id") if isinstance(data, dict) else None}
