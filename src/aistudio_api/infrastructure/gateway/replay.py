"""Captured request replay workflow."""

from __future__ import annotations

import logging

from aistudio_api.config import settings
from aistudio_api.infrastructure.gateway.capture import CapturedRequest
from aistudio_api.infrastructure.gateway.session import BrowserSession
from aistudio_api.infrastructure.request_logs import RequestLogStore

logger = logging.getLogger("aistudio")


class RequestReplayService:
    def __init__(self, session: BrowserSession | None, request_log_store: RequestLogStore | None = None):
        self._session = session
        self._request_log_store = request_log_store

    async def replay(
        self,
        captured: CapturedRequest | None,
        body: str,
        timeout: int | None = None,
        *,
        kind: str = "replay",
        model: str | None = None,
    ) -> tuple[int, bytes]:
        if not captured:
            return 0, b""

        if timeout is None:
            timeout = settings.timeout_replay

        headers = captured.replay_headers
        transport = "browser" if self._session is not None else "http"
        self._record_request(captured=captured, body=body, headers=headers, kind=kind, model=model, transport=transport)

        try:
            if self._session is not None:
                return await self._session.send_hooked_request(
                    body=body,
                    url=captured.url,
                    headers=headers,
                    timeout_ms=timeout * 1000,
                )

            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    captured.url,
                    data=body,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    raw = await resp.read()
                    return resp.status, raw
        except Exception as exc:
            logger.error("Replay error: %s", exc)
            return 0, str(exc).encode()

    def _record_request(
        self,
        *,
        captured: CapturedRequest,
        body: str,
        headers: dict[str, str],
        kind: str,
        model: str | None,
        transport: str,
    ) -> None:
        if self._request_log_store is None:
            return
        try:
            self._request_log_store.save(
                kind=kind,
                model=model or captured.model,
                method="POST",
                url=captured.url,
                headers=headers,
                captured_headers=captured.headers,
                body=body,
                transport=transport,
            )
        except Exception as exc:
            logger.warning("Request log write failed: %s", exc)
