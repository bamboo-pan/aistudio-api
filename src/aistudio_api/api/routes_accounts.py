"""账号管理路由。"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Depends, Request, Response
from pydantic import BaseModel

from aistudio_api.api.dependencies import get_account_service, get_runtime_state
from aistudio_api.infrastructure.account.login_service import LoginStatus

router = APIRouter(prefix="/accounts")


class LoginStartRequest(BaseModel):
    name: str | None = None


class LoginStartResponse(BaseModel):
    session_id: str


class AccountResponse(BaseModel):
    id: str
    name: str
    email: str | None
    created_at: str
    last_used: str | None


class LoginStatusResponse(BaseModel):
    session_id: str
    status: str
    account_id: str | None = None
    email: str | None = None
    error: str | None = None


class UpdateAccountRequest(BaseModel):
    name: str


class CredentialImportResponse(BaseModel):
    imported: list[AccountResponse]
    count: int


def _mark_sensitive_response(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def _to_account_response(account) -> AccountResponse:
    return AccountResponse(
        id=account.id,
        name=account.name,
        email=account.email,
        created_at=account.created_at,
        last_used=account.last_used,
    )


@router.post("/login/start", response_model=LoginStartResponse)
async def login_start(
    req: LoginStartRequest,
    account_service=Depends(get_account_service),
):
    """启动 Google 登录流程。"""
    session_id = await account_service.start_login(req.name)
    return LoginStartResponse(session_id=session_id)


@router.get("/login/status/{session_id}", response_model=LoginStatusResponse)
async def login_status(
    session_id: str,
    account_service=Depends(get_account_service),
    runtime_state=Depends(get_runtime_state),
):
    """查询登录状态。"""
    session = account_service.get_login_status(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="登录会话不存在")
    if session.status == LoginStatus.COMPLETED and session.account_id and not session.auth_activated:
        browser_session = runtime_state.client._session if runtime_state.client else None
        if browser_session is not None:
            account = await account_service.activate_account(
                session.account_id,
                browser_session,
                runtime_state.snapshot_cache,
                runtime_state.busy_lock,
            )
            if account is None:
                session.status = LoginStatus.FAILED
                session.error = "登录已保存，但切换浏览器认证状态失败"
            else:
                session.auth_activated = True
        else:
            session.auth_activated = True
    return LoginStatusResponse(
        session_id=session.session_id,
        status=session.status.value,
        account_id=session.account_id,
        email=session.email,
        error=session.error,
    )


@router.get("", response_model=list[AccountResponse])
async def list_accounts(
    account_service=Depends(get_account_service),
):
    """列出所有账号。"""
    accounts = account_service.list_accounts()
    return [
        _to_account_response(a)
        for a in accounts
    ]


@router.get("/active", response_model=AccountResponse)
async def get_active_account(
    account_service=Depends(get_account_service),
):
    """获取当前活跃账号。"""
    account = account_service.get_active_account()
    if account is None:
        raise HTTPException(status_code=404, detail="没有活跃账号")
    return _to_account_response(account)


@router.get("/export")
async def export_all_credentials(
    response: Response,
    account_service=Depends(get_account_service),
) -> dict[str, Any]:
    """导出所有账号凭证备份包。"""
    _mark_sensitive_response(response)
    try:
        return account_service.export_credentials()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=f"账号 {exc} 缺少 auth.json，无法导出") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{account_id}/export")
async def export_account_credentials(
    account_id: str,
    response: Response,
    account_service=Depends(get_account_service),
) -> dict[str, Any]:
    """导出单个账号凭证备份包。"""
    _mark_sensitive_response(response)
    try:
        return account_service.export_credentials(account_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="账号不存在") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=f"账号 {exc} 缺少 auth.json，无法导出") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/import", response_model=CredentialImportResponse)
async def import_credentials(
    request: Request,
    name: str | None = None,
    activate: bool = True,
    account_service=Depends(get_account_service),
):
    """导入凭证备份包或单账号 Playwright storage state。"""
    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="无效的 JSON 凭证内容") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="凭证内容必须是 JSON 对象")

    try:
        imported = account_service.import_credentials(payload, name=name, activate=activate)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return CredentialImportResponse(
        imported=[_to_account_response(account) for account in imported],
        count=len(imported),
    )


@router.post("/{account_id}/activate", response_model=AccountResponse)
async def activate_account(
    account_id: str,
    account_service=Depends(get_account_service),
    runtime_state=Depends(get_runtime_state),
):
    """切换到指定账号。"""
    # 从 runtime_state 获取 browser_session, snapshot_cache, busy_lock
    browser_session = runtime_state.client._session if runtime_state.client else None
    snapshot_cache = runtime_state.snapshot_cache
    busy_lock = runtime_state.busy_lock

    if browser_session is None:
        raise HTTPException(status_code=503, detail="服务未就绪")

    account = await account_service.activate_account(
        account_id, browser_session, snapshot_cache, busy_lock
    )
    if account is None:
        raise HTTPException(status_code=404, detail="账号不存在或切换失败")
    return _to_account_response(account)


@router.delete("/{account_id}")
async def delete_account(
    account_id: str,
    account_service=Depends(get_account_service),
):
    """删除账号。"""
    success = account_service.delete_account(account_id)
    if not success:
        raise HTTPException(status_code=404, detail="账号不存在")
    return {"ok": True}


@router.put("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: str,
    req: UpdateAccountRequest,
    account_service=Depends(get_account_service),
):
    """更新账号名称。"""
    account = account_service.update_account(account_id, req.name)
    if account is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    return _to_account_response(account)
