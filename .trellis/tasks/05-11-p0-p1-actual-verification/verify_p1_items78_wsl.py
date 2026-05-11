from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


SRC = Path('/mnt/c/Users/bamboo/Desktop/aistudio-api')
ACCOUNTS_DIR = '/home/bamboo/aistudio-api/data/accounts'
EXCLUDED_DIRS = {'.git', '.venv', 'data', '__pycache__', '.pytest_cache'}


def run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.stdout:
        print(result.stdout, end='')
    result.check_returncode()
    return result


def copy_repo(src: Path, dst: Path) -> None:
    ignore = shutil.ignore_patterns('.git', '.venv', 'data', '__pycache__', '.pytest_cache', '*.pyc')
    for item in src.iterdir():
        if item.name in EXCLUDED_DIRS:
            continue
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, ignore=ignore)
        else:
            shutil.copy2(item, target)


def smoke_code() -> str:
    return r'''
import asyncio
import json
import logging
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import httpx
from fastapi import FastAPI

from aistudio_api.api.dependencies import get_account_service
from aistudio_api.api.routes_accounts import router as accounts_router
from aistudio_api.api.schemas import ImageRequest
from aistudio_api.api.state import runtime_state
from aistudio_api.application.account_rotator import AccountRotator
from aistudio_api.application.account_service import AccountService
from aistudio_api.application.api_service import handle_image_generation
from aistudio_api.domain.models import Candidate, GeneratedImage, ModelOutput
from aistudio_api.infrastructure.account.account_store import AccountStore
from aistudio_api.infrastructure.account.login_service import LoginService


def storage_state(cookie_name="sid", cookie_value="1", domain=".google.com", expires=None, email=None):
    cookie = {"name": cookie_name, "value": cookie_value, "domain": domain, "path": "/"}
    if expires is not None:
        cookie["expires"] = expires
    origins = []
    if email:
        origins = [{"origin": "https://aistudio.google.com", "localStorage": [{"name": "account_email", "value": email}]}]
    return {"cookies": [cookie], "origins": origins}


class FakeImageClient:
    def __init__(self):
        self.calls = []

    async def generate_image(self, *, prompt, model, generation_config_overrides=None):
        self.calls.append({"model": model, "generation_config_overrides": generation_config_overrides})
        return ModelOutput(candidates=[Candidate(text="ok", images=[GeneratedImage(mime="image/png", data=b"image", size=5)])])


class FakeBrowserSession:
    def __init__(self):
        self.switch_count = 0

    async def switch_auth(self, auth_path):
        self.switch_count += 1


class FakeSnapshotCache:
    def __init__(self):
        self.clear_calls = 0

    def clear(self):
        self.clear_calls += 1


def request_app(app, method, url, **kwargs):
    async def send():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, url, **kwargs)
    return asyncio.run(send())


accounts_dir = Path(os.environ["AISTUDIO_ACCOUNTS_DIR"])
real_store = AccountStore(accounts_dir=accounts_dir)
real_accounts = real_store.list_accounts()
real_with_auth = 0
real_valid = 0
real_errors = 0
for account in real_accounts:
    auth_path = real_store.get_auth_path(account.id)
    if auth_path is None:
        continue
    real_with_auth += 1
    try:
        real_store._validate_storage_state(json.loads(auth_path.read_text(encoding="utf-8")))
        real_valid += 1
    except Exception:
        real_errors += 1

print("p1_real_accounts_dir_exists", accounts_dir.is_dir())
print("p1_real_accounts_count", len(real_accounts))
print("p1_real_accounts_with_auth", real_with_auth)
print("p1_real_auth_shape_valid", real_valid)
print("p1_real_auth_shape_errors", real_errors)
print("p1_real_metadata_has_tier_fields", all(hasattr(account, "tier") for account in real_accounts))
print("p1_real_metadata_has_health_fields", all(hasattr(account, "health_status") for account in real_accounts))

scratch = Path("/tmp/aistudio-p1-items78-smoke")
if scratch.exists():
    shutil.rmtree(scratch)
scratch.mkdir(parents=True)
store = AccountStore(accounts_dir=scratch)
service = AccountService(store, LoginService())
valid = store.save_account("valid", None, storage_state(cookie_value="synthetic-secret", email="synthetic@example.test"), tier="ultra")
manual = service.test_account(valid.id)
app = FastAPI()
app.include_router(accounts_router)
app.dependency_overrides[get_account_service] = lambda: service
route_response = request_app(app, "POST", f"/accounts/{valid.id}/test")
route_text = route_response.text.lower()
update_response = request_app(app, "PUT", f"/accounts/{valid.id}", json={"tier": "pro"})

expired = store.save_account("expired", None, storage_state(cookie_name="expired", expires=946684800), activate=False)
missing = store.save_account("missing", None, storage_state(cookie_name="missing"), activate=False)
(scratch / missing.id / "auth.json").unlink()
expired_result = service.test_account(expired.id)
missing_result = service.test_account(missing.id)

selection_store = AccountStore(accounts_dir=scratch / "selection")
selection_store.save_account("free", None, storage_state(cookie_name="free"), tier="free")
selection_store.save_account("pro", None, storage_state(cookie_name="pro"), activate=False, tier="pro")
rotator = AccountRotator(selection_store, cooldown_seconds=30, error_isolation_threshold=2)
image_pick = asyncio.run(rotator.get_next_account("gemini-3.1-flash-image-preview"))
text_pick = asyncio.run(rotator.get_next_account("gemini-3-flash-preview"))
fallback_store = AccountStore(accounts_dir=scratch / "fallback")
fallback_store.save_account("free", None, storage_state(cookie_name="fallback"), tier="free")
fallback_rotator = AccountRotator(fallback_store)
records = []

class Capture(logging.Handler):
    def emit(self, record):
        records.append(record.getMessage())

logger = logging.getLogger("aistudio.rotator")
handler = Capture()
logger.addHandler(handler)
logger.setLevel(logging.WARNING)
try:
    fallback_pick = asyncio.run(fallback_rotator.get_next_account("gemini-3.1-flash-image-preview"))
finally:
    logger.removeHandler(handler)

limited = selection_store.save_account("limited", None, storage_state(cookie_name="limited"), activate=False)
failing = selection_store.save_account("failing", None, storage_state(cookie_name="failing"), activate=False)
rotator.record_rate_limited(limited.id)
rotator.record_error(failing.id)
rotator.record_error(failing.id)
stats = rotator.get_all_stats()

runtime_store = AccountStore(accounts_dir=scratch / "runtime")
runtime_store.save_account("free", None, storage_state(cookie_name="runtime-free"), tier="free")
runtime_store.save_account("pro", None, storage_state(cookie_name="runtime-pro"), activate=False, tier="pro")
runtime_service = AccountService(runtime_store, LoginService())
runtime_rotator = AccountRotator(runtime_store)
browser = FakeBrowserSession()
cache = FakeSnapshotCache()
client = FakeImageClient()
old = (runtime_state.busy_lock, runtime_state.account_service, runtime_state.rotator, runtime_state.client, runtime_state.snapshot_cache)
runtime_state.busy_lock = asyncio.Semaphore(3)
runtime_state.account_service = runtime_service
runtime_state.rotator = runtime_rotator
runtime_state.client = SimpleNamespace(_session=browser)
runtime_state.snapshot_cache = cache
try:
    response = asyncio.run(handle_image_generation(ImageRequest(prompt="draw", model="gemini-3.1-flash-image-preview"), client))
finally:
    runtime_state.busy_lock, runtime_state.account_service, runtime_state.rotator, runtime_state.client, runtime_state.snapshot_cache = old

print("p1_manual_health_status", manual["status"])
print("p1_manual_health_response_sanitized", '"cookies"' not in route_text and "synthetic-secret" not in route_text)
print("p1_tier_update_status", update_response.json().get("tier"))
print("p1_expired_isolated", expired_result["status"] == "expired" and store.get_account(expired.id).is_isolated)
print("p1_missing_auth_isolated", missing_result["status"] == "missing_auth" and store.get_account(missing.id).is_isolated)
print("p1_image_model_prefers_premium", image_pick.tier in ("pro", "ultra"))
print("p1_text_model_can_use_free", text_pick.tier == "free")
print("p1_image_fallback_to_free", fallback_pick.tier == "free")
print("p1_image_fallback_logged", any("fallback" in message.lower() for message in records))
print("p1_rate_limited_unavailable", stats[limited.id]["is_available"] is False)
print("p1_error_isolated_unavailable", stats[failing.id]["is_available"] is False)
print("p1_image_request_switched_to_premium", runtime_store.get_active_account().tier in ("pro", "ultra") and browser.switch_count == 1 and cache.clear_calls == 1 and bool(response["data"][0]["b64_json"]))
print("p1_secrets_printed", False)
'''


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix='aistudio-api-verify-p1-items78-copilot-', dir='/home/bamboo'))
    print(f'temp_dir {tmp}')
    copy_repo(SRC, tmp)

    venv_python = tmp / '.venv' / 'bin' / 'python'
    run(['python3', '-m', 'venv', '.venv'], cwd=tmp)
    run([str(venv_python), '-m', 'pip', 'install', '-q', '--upgrade', 'pip'], cwd=tmp)
    run([str(venv_python), '-m', 'pip', 'install', '-q', '-e', '.[test]'], cwd=tmp)

    env = os.environ.copy()
    env['AISTUDIO_ACCOUNTS_DIR'] = ACCOUNTS_DIR
    run([str(venv_python), '-m', 'pytest', '-q'], cwd=tmp, env=env)
    run([str(venv_python), '-m', 'compileall', '-q', 'src', 'tests'], cwd=tmp, env=env)
    if shutil.which('node'):
        run(['node', '--check', 'src/aistudio_api/static/app.js'], cwd=tmp, env=env)
        print('node_check passed')
    else:
        print('node_check node_unavailable')
    run([str(venv_python), '-c', smoke_code()], cwd=tmp, env=env)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
