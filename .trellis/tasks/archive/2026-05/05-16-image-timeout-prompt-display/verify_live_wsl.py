from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

SRC = Path("/mnt/c/Users/bamboo/Desktop/aistudio-api_u3")
ACCOUNTS_DIR = "/home/bamboo/aistudio-api/data/accounts"
DEFAULT_WSL_PROXY = "http://192.168.128.1:7890"
EXCLUDED_DIRS = {".git", ".venv", "data", "__pycache__", ".pytest_cache"}


def sanitize(text: str) -> str:
    text = re.sub(r"/home/bamboo/aistudio-api/data/accounts/[^\s'\"]+", "[REDACTED_ACCOUNT_PATH]", text)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", text)
    return text


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 300,
    allow_fail: bool = False,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    if result.stdout:
        print(sanitize(result.stdout), end="")
    if result.returncode and not allow_fail:
        raise subprocess.CalledProcessError(result.returncode, command, output=result.stdout)
    return result


def copy_repo(src: Path, dst: Path) -> None:
    ignore = shutil.ignore_patterns(".git", ".venv", "data", "__pycache__", ".pytest_cache", "*.pyc")
    for item in src.iterdir():
        if item.name in EXCLUDED_DIRS:
            continue
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, ignore=ignore)
        else:
            shutil.copy2(item, target)


def live_smoke_code() -> str:
    return r'''
import asyncio
import json
import logging
import os
import re
from pathlib import Path

import httpx


def sanitize(text):
    text = re.sub(r"/home/bamboo/aistudio-api/data/accounts/[^\s'\"]+", "[REDACTED_ACCOUNT_PATH]", str(text))
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", text)
    return text


logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")

from aistudio_api.api.app import app
from aistudio_api.api.state import runtime_state
from aistudio_api.application.account_service import AccountService
from aistudio_api.config import settings
from aistudio_api.infrastructure.account.account_store import AccountStore
from aistudio_api.infrastructure.account.login_service import LoginService
from aistudio_api.infrastructure.gateway.client import AIStudioClient, _snapshot_cache


async def request_json(http, method, path, payload):
    response = await http.request(method, path, json=payload, timeout=300)
    try:
        body = response.json()
    except Exception:
        body = {"raw": response.text[:500]}
    return response.status_code, body, response.text


def openai_error_message(body):
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        return error.get("message") or ""
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, dict):
        return detail.get("message") or ""
    return str(body)[:500]


async def main():
    accounts_dir = Path(os.environ["AISTUDIO_ACCOUNTS_DIR"])
    store = AccountStore(accounts_dir=accounts_dir)
    accounts = store.list_accounts()
    auth_path = store.get_active_auth_path()
    if auth_path is None or not auth_path.exists():
        for account in accounts:
            candidate = store.get_auth_path(account.id)
            if candidate is not None and candidate.exists():
                auth_path = candidate
                break

    print("live_accounts_dir_exists", accounts_dir.is_dir())
    print("live_accounts_count", len(accounts))
    print("live_auth_available", auth_path is not None and auth_path.exists())
    print("live_timeout_replay", settings.timeout_replay)
    if settings.timeout_replay != 241:
        return 3
    if auth_path is None or not auth_path.exists():
        return 2

    try:
        store._validate_storage_state(json.loads(auth_path.read_text(encoding="utf-8")))
        print("live_auth_shape_valid", True)
    except Exception as exc:
        print("live_auth_shape_valid", False)
        print("live_auth_shape_error", sanitize(exc.__class__.__name__))
        return 2

    client = AIStudioClient(port=int(os.environ.get("AISTUDIO_CAMOUFOX_PORT", "19437")))
    await client.switch_auth(str(auth_path))
    runtime_state.client = client
    runtime_state.busy_lock = asyncio.Semaphore(1)
    runtime_state.snapshot_cache = _snapshot_cache
    runtime_state.account_service = AccountService(store, LoginService())
    runtime_state.rotator = None

    image_ok = False
    prompt_options_ok = False
    try:
        try:
            await client.warmup()
            print("live_browser_warmup_ok", True)
        except Exception as exc:
            print("live_browser_warmup_ok", False)
            print("live_browser_warmup_error_type", exc.__class__.__name__)
            print("live_browser_warmup_error", sanitize(str(exc))[:500])
            return 2

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
            prompt_status, prompt_body, _ = await request_json(
                http,
                "POST",
                "/v1/images/prompt-optimizations",
                {
                    "model": "gemini-3-flash-preview",
                    "prompt": "一只小猫坐在溪流边，写实摄影",
                    "style_template": "photorealistic",
                    "thinking": "off",
                },
            )
            options = prompt_body.get("options", []) if isinstance(prompt_body, dict) else []
            prompt_options_ok = prompt_status == 200 and len(options) == 3 and all(item.get("prompt") for item in options)
            print("live_prompt_optimization_status", prompt_status)
            print("live_prompt_optimization_options", len(options))
            if not prompt_options_ok:
                print("live_prompt_optimization_error", sanitize(openai_error_message(prompt_body))[:500])

            image_status, image_body, image_text = await request_json(
                http,
                "POST",
                "/v1/images/generations",
                {
                    "model": "gemini-3.1-flash-image-preview",
                    "prompt": "A small blue square on a plain white background. No text.",
                    "size": "512x512",
                    "n": 1,
                    "response_format": "b64_json",
                },
            )
            image_items = image_body.get("data", []) if isinstance(image_body, dict) else []
            image_b64_len = 0
            if image_items and isinstance(image_items[0], dict):
                image_b64_len = len(image_items[0].get("b64_json") or "")
            image_ok = image_status == 200 and image_b64_len > 0
            print("live_image_status", image_status)
            print("live_image_returned", image_ok)
            print("live_image_b64_len", image_b64_len)
            print("live_image_error_mentions_timeout", "timeout" in image_text.lower())
            if image_status != 200:
                print("live_image_error_type", image_body.get("error", {}).get("type") if isinstance(image_body, dict) else None)
                print("live_image_error", sanitize(openai_error_message(image_body))[:500])
    except Exception as exc:
        print("live_validation_exception_type", exc.__class__.__name__)
        print("live_validation_exception", sanitize(str(exc))[:800])
    finally:
        runtime_state.client = None
        runtime_state.busy_lock = None
        runtime_state.account_service = None
        runtime_state.rotator = None
        runtime_state.snapshot_cache = None
        if getattr(client, "_session", None) is not None:
            try:
                await client._session._run_sync(client._session._close_sync)
            except Exception:
                pass

    print("live_prompt_options_ok", prompt_options_ok)
    print("live_image_ok", image_ok)
    print("live_secrets_printed", False)
    return 0 if prompt_options_ok and image_ok else 1


raise SystemExit(asyncio.run(main()))
'''


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="aistudio-api-u3-live-", dir="/home/bamboo"))
    print(f"temp_dir {tmp}")
    copy_repo(SRC, tmp)

    venv_python = tmp / ".venv" / "bin" / "python"
    run(["python3", "-m", "venv", ".venv"], cwd=tmp, timeout=300)
    run([str(venv_python), "-m", "pip", "install", "-q", "--upgrade", "pip"], cwd=tmp, timeout=600)
    run([str(venv_python), "-m", "pip", "install", "-q", "-e", ".[test]"], cwd=tmp, timeout=900)

    fetch_ok = False
    camoufox_bin = tmp / ".venv" / "bin" / "camoufox"
    if camoufox_bin.exists():
        result = run([str(camoufox_bin), "fetch"], cwd=tmp, timeout=900, allow_fail=True)
        fetch_ok = result.returncode == 0
    if not fetch_ok:
        result = run([str(venv_python), "-m", "camoufox", "fetch"], cwd=tmp, timeout=900, allow_fail=True)
        fetch_ok = result.returncode == 0
    print("camoufox_fetch_ok", fetch_ok)

    env = os.environ.copy()
    env["AISTUDIO_ACCOUNTS_DIR"] = ACCOUNTS_DIR
    env["AISTUDIO_CAMOUFOX_HEADLESS"] = "1"
    env["AISTUDIO_CAMOUFOX_PORT"] = "19437"
    env["AISTUDIO_LOGIN_CAMOUFOX_PORT"] = "19438"
    env["AISTUDIO_TIMEOUT_CAPTURE"] = "120"
    env["AISTUDIO_TIMEOUT_REPLAY"] = "241"
    env["AISTUDIO_TIMEOUT_STREAM"] = "180"
    env["AISTUDIO_DUMP_RAW_RESPONSE"] = "0"
    proxy_server = env.get("AISTUDIO_PROXY_SERVER") or DEFAULT_WSL_PROXY
    env["AISTUDIO_PROXY_SERVER"] = proxy_server
    env.setdefault("HTTPS_PROXY", proxy_server)
    env.setdefault("HTTP_PROXY", proxy_server)
    return run([str(venv_python), "-c", live_smoke_code()], cwd=tmp, env=env, timeout=1500, allow_fail=True).returncode


if __name__ == "__main__":
    raise SystemExit(main())
