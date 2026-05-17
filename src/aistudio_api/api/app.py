"""FastAPI application entrypoint."""

from __future__ import annotations

import argparse
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from aistudio_api.infrastructure.generated_images import GeneratedImageStore
from aistudio_api.infrastructure.gateway.client import AIStudioClient

from .routes_accounts import router as accounts_router
from .routes_gemini import router as gemini_router
from .routes_generated_images import register_generated_image_routes
from .routes_image_sessions import router as image_sessions_router
from .routes_openai import router as openai_router
from .routes_system import router as system_router
from .state import runtime_state

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("aistudio.server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    from aistudio_api.config import settings
    from aistudio_api.infrastructure.account.account_store import AccountStore
    from aistudio_api.infrastructure.account.login_service import LoginService
    from aistudio_api.application.account_service import AccountService
    from aistudio_api.application.account_rotator import init_rotator, RotationMode
    from aistudio_api.application.account_client_pool import AccountClientPool

    client = AIStudioClient(
        port=runtime_state.camoufox_port,
        use_pure_http=settings.use_pure_http,
    )
    runtime_state.client = client
    from aistudio_api.config import settings as app_settings
    runtime_state.busy_lock = asyncio.Semaphore(app_settings.max_concurrency)

    # 注入 snapshot 缓存引用，切号时需要清除
    from aistudio_api.infrastructure.gateway.client import _snapshot_cache
    runtime_state.snapshot_cache = _snapshot_cache

    # 初始化账号管理服务
    account_store = AccountStore()
    login_service = LoginService(port=settings.login_camoufox_port)
    account_service = AccountService(account_store, login_service)
    runtime_state.account_service = account_service

    active_auth_path = account_store.get_active_auth_path()
    if active_auth_path is not None:
        await client.switch_auth(str(active_auth_path))
        if active_auth_path.exists():
            logger.info("Loaded active account auth state: %s", active_auth_path)
        else:
            logger.warning("Active account auth state file is missing: %s", active_auth_path)

    # 初始化账号轮询器
    rotation_mode = getattr(settings, "account_rotation_mode", "round_robin")
    cooldown = getattr(settings, "account_cooldown_seconds", 60)
    rotator = init_rotator(
        account_store,
        mode=RotationMode(rotation_mode),
        cooldown_seconds=cooldown,
    )
    runtime_state.rotator = rotator
    runtime_state.account_client_pool = AccountClientPool(
        account_store,
        port=runtime_state.camoufox_port,
        use_pure_http=settings.use_pure_http,
    )

    logger.info(
        "Client initialized (camoufox port=%s, rotation=%s, accounts=%d)",
        runtime_state.camoufox_port,
        rotator.mode,
        len(account_store.list_accounts()),
    )

    # 后台预热浏览器，避免首次请求延迟
    warmup_task = None
    if not settings.use_pure_http:
        async def _warmup():
            try:
                await client.warmup()
            except Exception as e:
                logger.warning("浏览器预热失败: %s", e)
        warmup_task = asyncio.create_task(_warmup())

    yield
    logger.info("Shutting down")
    if warmup_task and not warmup_task.done():
        warmup_task.cancel()
    if runtime_state.account_client_pool is not None:
        await runtime_state.account_client_pool.close()
    await client.close()
    runtime_state.client = None
    runtime_state.busy_lock = None
    runtime_state.account_service = None
    runtime_state.rotator = None
    runtime_state.account_client_pool = None


app = FastAPI(title="AI Studio API", lifespan=lifespan)
app.include_router(system_router)
app.include_router(gemini_router)
app.include_router(openai_router)
app.include_router(accounts_router)
app.include_router(image_sessions_router)
register_generated_image_routes(app)


def _is_openai_compat_path(request: Request) -> bool:
    path = request.url.path
    return path == "/v1" or path.startswith("/v1/")


def _detail_from_exception(status_code: int, detail) -> dict:
    if isinstance(detail, dict):
        return detail
    error_type = "bad_request"
    if status_code == 401:
        error_type = "authentication_error"
    elif status_code == 404:
        error_type = "not_found"
    elif status_code == 429:
        error_type = "rate_limit_exceeded"
    elif status_code == 503:
        error_type = "service_unavailable"
    elif status_code >= 500:
        error_type = "server_error"
    return {"message": str(detail), "type": error_type}


def _openai_error_content(detail: dict) -> dict:
    error_type = detail.get("type") or "invalid_request_error"
    if error_type in {"bad_request", "not_found", "unsupported_feature"}:
        error_type = "invalid_request_error"
    return {
        "error": {
            "message": detail.get("message", "Request failed"),
            "type": error_type,
            "param": detail.get("param"),
            "code": detail.get("code"),
        }
    }


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(part) for part in first.get("loc", []) if part != "body")
    message = first.get("msg", "Invalid request body")
    if location:
        message = f"{location}: {message}"
    detail = {"message": message, "type": "bad_request"}
    content = _openai_error_content(detail) if _is_openai_compat_path(request) else {"detail": detail}
    return JSONResponse(status_code=400, content=content)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = _detail_from_exception(exc.status_code, exc.detail)
    content = _openai_error_content(detail) if _is_openai_compat_path(request) else {"detail": detail}
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)

# 挂载静态文件
import os
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

generated_image_store = GeneratedImageStore()
generated_image_store.ensure_directory()
app.mount(
    generated_image_store.public_route,
    StaticFiles(directory=str(generated_image_store.root)),
    name="generated-images",
)


@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")


def main():
    from aistudio_api.config import settings

    parser = argparse.ArgumentParser(description="AI Studio OpenAI-compatible API Server")
    parser.add_argument("--port", type=int, default=settings.port)
    parser.add_argument("--camoufox-port", type=int, default=settings.camoufox_port)
    args = parser.parse_args()

    runtime_state.camoufox_port = args.camoufox_port

    import uvicorn

    logger.info("Starting server on port %s", args.port)
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")
