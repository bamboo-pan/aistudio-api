"""OpenAI-compatible API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from aistudio_api.application.api_service import handle_chat, handle_image_generation
from aistudio_api.domain.model_capabilities import get_model_metadata, list_model_metadata
from aistudio_api.infrastructure.gateway.client import AIStudioClient

from .dependencies import get_client
from .schemas import ChatRequest, ImageRequest

router = APIRouter()


@router.get("/v1/models")
async def list_models():
    return {"object": "list", "data": list_model_metadata()}


@router.get("/v1/models/{model_id:path}")
async def get_model(model_id: str):
    try:
        return get_model_metadata(model_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"message": str(exc), "type": "invalid_request_error"}) from exc


@router.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest, client: AIStudioClient = Depends(get_client)):
    return await handle_chat(req, client)


@router.post("/v1/images/generations")
async def image_generations(req: ImageRequest, client: AIStudioClient = Depends(get_client)):
    return await handle_image_generation(req, client)

