from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


SRC = Path("/mnt/c/Users/bamboo/Desktop/aistudio-api_u2")
ACCOUNTS_DIR = "/home/bamboo/aistudio-api/data/accounts"
DEFAULT_WSL_PROXY = "http://192.168.128.1:7890"
EXCLUDED_DIRS = {".git", ".venv", "data", "__pycache__", ".pytest_cache"}


def sanitize(text: object) -> str:
    value = str(text)
    value = re.sub(r"/home/bamboo/aistudio-api/data/accounts/[^\s'\"]+", "[REDACTED_ACCOUNT_PATH]", value)
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", value)
    return value


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
import logging
import os
import re
from pathlib import Path

import httpx


def sanitize(text):
    value = str(text)
    value = re.sub(r"/home/bamboo/aistudio-api/data/accounts/[^\s'\"]+", "[REDACTED_ACCOUNT_PATH]", value)
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", value)
    return value


def openai_error_message(body):
    if not isinstance(body, dict):
        return str(body)[:500]
    error = body.get("error")
    if isinstance(error, dict):
        return error.get("message") or ""
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("message") or ""
    return str(body)[:500]


logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")

from aistudio_api.api.app import app
from aistudio_api.api.state import runtime_state
from aistudio_api.application.account_rotator import AccountRotator
from aistudio_api.application.account_service import AccountService
from aistudio_api.infrastructure.account.account_store import AccountStore
from aistudio_api.infrastructure.account.login_service import LoginService
from aistudio_api.infrastructure.gateway.client import AIStudioClient, _snapshot_cache


async def main():
    accounts_dir = Path(os.environ["AISTUDIO_ACCOUNTS_DIR"])
    store = AccountStore(accounts_dir=accounts_dir)
    accounts = store.list_accounts()
    premium_accounts = [account for account in accounts if account.is_premium and not account.is_isolated]
    non_premium_accounts = [account for account in accounts if not account.is_premium and not account.is_isolated]
    print("live_accounts_dir_exists", accounts_dir.is_dir())
    print("live_accounts_count", len(accounts))
    print("live_premium_count", len(premium_accounts))
    print("live_non_premium_count", len(non_premium_accounts))
    if not accounts or not premium_accounts:
        print("live_validation_skipped", "no available Pro/Ultra account")
        return 2

    initial_account = non_premium_accounts[0] if non_premium_accounts else premium_accounts[0]
    store.set_active_account(initial_account.id)
    rotator = AccountRotator(store)
    print("live_pro_model_prefers_premium", rotator.model_prefers_premium("gemini-3.1-pro-preview"))
    print("live_prefixed_pro_model_prefers_premium", rotator.model_prefers_premium("models/gemini-3.1-pro-preview"))
    print("live_initial_account_premium", initial_account.is_premium)

    initial_auth_path = store.get_auth_path(initial_account.id)
    if initial_auth_path is None:
        print("live_validation_skipped", "initial account missing auth")
        return 2

    client = AIStudioClient(port=int(os.environ.get("AISTUDIO_CAMOUFOX_PORT", "19567")))
    chat_ok = False
    switched_to_premium = False
    try:
        await client.switch_auth(str(initial_auth_path))
        runtime_state.client = client
        runtime_state.busy_lock = asyncio.Semaphore(1)
        runtime_state.snapshot_cache = _snapshot_cache
        runtime_state.account_service = AccountService(store, LoginService())
        runtime_state.rotator = rotator

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
            response = await http.post(
                "/v1/chat/completions",
                json={
                    "model": "gemini-3.1-pro-preview",
                    "messages": [{"role": "user", "content": "Reply exactly OK."}],
                    "stream": False,
                    "thinking": "off",
                },
                timeout=420,
            )
            try:
                body = response.json()
            except Exception:
                body = {"raw": response.text[:500]}
            choices = body.get("choices", []) if isinstance(body, dict) else []
            active = store.get_active_account()
            switched_to_premium = bool(active and active.is_premium)
            chat_ok = response.status_code == 200 and bool(choices) and switched_to_premium
            print("live_pro_chat_status", response.status_code)
            print("live_pro_chat_choices", len(choices) if isinstance(choices, list) else 0)
            print("live_after_account_premium", switched_to_premium)
            print("live_selection_reason", rotator.last_selection_reason)
            if response.status_code != 200:
                print("live_pro_chat_error", sanitize(openai_error_message(body))[:500])
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

    print("live_pro_route_ok", chat_ok)
    print("live_secrets_printed", False)
    return 0 if chat_ok else 1


raise SystemExit(asyncio.run(main()))
'''


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="aistudio-api-u2-new-account-permission-", dir="/home/bamboo"))
    print(f"temp_dir {tmp}")
    copy_repo(SRC, tmp)

    venv_python = tmp / ".venv" / "bin" / "python"
    run(["python3", "-m", "venv", ".venv"], cwd=tmp, timeout=300)
    run([str(venv_python), "-m", "pip", "install", "-q", "--upgrade", "pip"], cwd=tmp, timeout=600)
    run([str(venv_python), "-m", "pip", "install", "-q", "-e", ".[test]"], cwd=tmp, timeout=900)

    camoufox_fetch_ok = False
    camoufox_bin = tmp / ".venv" / "bin" / "camoufox"
    if camoufox_bin.exists():
        result = run([str(camoufox_bin), "fetch"], cwd=tmp, timeout=900, allow_fail=True)
        camoufox_fetch_ok = result.returncode == 0
    if not camoufox_fetch_ok:
        result = run([str(venv_python), "-m", "camoufox", "fetch"], cwd=tmp, timeout=900, allow_fail=True)
        camoufox_fetch_ok = result.returncode == 0
    print("camoufox_fetch_ok", camoufox_fetch_ok)

    env = os.environ.copy()
    env["AISTUDIO_ACCOUNTS_DIR"] = ACCOUNTS_DIR
    env["AISTUDIO_CAMOUFOX_HEADLESS"] = "1"
    env["AISTUDIO_CAMOUFOX_PORT"] = "19567"
    env["AISTUDIO_LOGIN_CAMOUFOX_PORT"] = "19568"
    env["AISTUDIO_TIMEOUT_CAPTURE"] = "120"
    env["AISTUDIO_TIMEOUT_REPLAY"] = "180"
    env["AISTUDIO_TIMEOUT_STREAM"] = "180"
    env["AISTUDIO_DUMP_RAW_RESPONSE"] = "0"
    proxy_server = env.get("AISTUDIO_PROXY_SERVER") or DEFAULT_WSL_PROXY
    env["AISTUDIO_PROXY_SERVER"] = proxy_server
    env.setdefault("HTTPS_PROXY", proxy_server)
    env.setdefault("HTTP_PROXY", proxy_server)

    run(
        [
            str(venv_python),
            "-m",
            "pytest",
            "tests/unit/test_account_health_and_selection.py",
            "tests/unit/test_model_capabilities.py",
            "-q",
        ],
        cwd=tmp,
        env=env,
        timeout=300,
    )
    return run([str(venv_python), "-c", live_smoke_code()], cwd=tmp, env=env, timeout=1500, allow_fail=True).returncode


if __name__ == "__main__":
    raise SystemExit(main())