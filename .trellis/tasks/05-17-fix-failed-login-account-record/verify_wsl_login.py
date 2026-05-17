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
import json
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


logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")

from aistudio_api.api.app import app
from aistudio_api.api.state import runtime_state
from aistudio_api.application.account_service import AccountService
from aistudio_api.infrastructure.account.account_store import AccountStore
from aistudio_api.infrastructure.account.login_service import LoginService
from aistudio_api.infrastructure.gateway.client import AIStudioClient, _snapshot_cache


def auth_candidates(store):
    seen = set()
    candidates = []
    active_path = store.get_active_auth_path()
    if active_path is not None and active_path.exists():
        candidates.append(active_path)
        seen.add(str(active_path))
    for account in store.list_accounts():
        candidate = store.get_auth_path(account.id)
        if candidate is not None and candidate.exists() and str(candidate) not in seen:
            candidates.append(candidate)
            seen.add(str(candidate))
    return candidates


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


async def main():
    accounts_dir = Path(os.environ["AISTUDIO_ACCOUNTS_DIR"])
    store = AccountStore(accounts_dir=accounts_dir)
    accounts = store.list_accounts()
    candidates = auth_candidates(store)
    print("live_accounts_dir_exists", accounts_dir.is_dir())
    print("live_accounts_count", len(accounts))
    print("live_auth_candidates", len(candidates))
    if not candidates:
        return 2

    client = AIStudioClient(port=int(os.environ.get("AISTUDIO_CAMOUFOX_PORT", "19557")))
    chat_ok = False
    try:
        runtime_state.client = client
        runtime_state.busy_lock = asyncio.Semaphore(1)
        runtime_state.snapshot_cache = _snapshot_cache
        runtime_state.account_service = AccountService(store, LoginService())
        runtime_state.rotator = None

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
            for index, auth_path in enumerate(candidates, start=1):
                try:
                    detected_email = store.validate_storage_state(json.loads(auth_path.read_text(encoding="utf-8")))
                    print(f"live_auth_{index}_shape_valid", True)
                    print(f"live_auth_{index}_email_detected", bool(detected_email))
                except Exception as exc:
                    print(f"live_auth_{index}_shape_valid", False)
                    print(f"live_auth_{index}_shape_error_type", exc.__class__.__name__)
                    print(f"live_auth_{index}_shape_error", sanitize(str(exc))[:500])
                    continue

                await client.switch_auth(str(auth_path))
                await client.warmup()
                print(f"live_browser_{index}_warmup_ok", True)
                response = await http.post(
                    "/v1/chat/completions",
                    json={
                        "model": "gemini-3-flash-preview",
                        "messages": [{"role": "user", "content": "Reply exactly OK."}],
                        "stream": False,
                        "thinking": "off",
                    },
                    timeout=360,
                )
                try:
                    body = response.json()
                except Exception:
                    body = {"raw": response.text[:500]}
                choices = body.get("choices", []) if isinstance(body, dict) else []
                chat_ok = response.status_code == 200 and bool(choices)
                print(f"live_chat_{index}_status", response.status_code)
                print(f"live_chat_{index}_choices", len(choices) if isinstance(choices, list) else 0)
                if response.status_code != 200:
                    print(f"live_chat_{index}_error", sanitize(openai_error_message(body))[:500])
                if chat_ok:
                    break
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

    print("live_chat_ok", chat_ok)
    print("live_secrets_printed", False)
    return 0 if chat_ok else 1


raise SystemExit(asyncio.run(main()))
'''


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="aistudio-api-u2-login-verify-", dir="/home/bamboo"))
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
    env["AISTUDIO_CAMOUFOX_PORT"] = "19557"
    env["AISTUDIO_LOGIN_CAMOUFOX_PORT"] = "19558"
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
            "tests/unit/test_login_service.py",
            "tests/unit/test_account_auth_activation.py",
            "tests/unit/test_account_credentials.py",
            "-q",
        ],
        cwd=tmp,
        env=env,
        timeout=300,
    )
    return run([str(venv_python), "-c", live_smoke_code()], cwd=tmp, env=env, timeout=1500, allow_fail=True).returncode


if __name__ == "__main__":
    raise SystemExit(main())
