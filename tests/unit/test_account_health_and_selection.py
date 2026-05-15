import asyncio
import json
import logging
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
from fastapi import FastAPI

from aistudio_api.api.dependencies import get_account_service
from aistudio_api.api.routes_accounts import router as accounts_router
from aistudio_api.api.schemas import ImageRequest
from aistudio_api.api.state import runtime_state
from aistudio_api.config import settings
from aistudio_api.application.account_rotator import AccountRotator, RotationMode
from aistudio_api.application.account_service import AccountService
from aistudio_api.application.api_service import handle_image_generation
from aistudio_api.domain.models import Candidate, GeneratedImage, ModelOutput
from aistudio_api.infrastructure.account.account_store import AccountStore
from aistudio_api.infrastructure.account.login_service import LoginService
from aistudio_api.infrastructure.account.tier_detector import AccountTier, TierResult


def storage_state(cookie_name="sid", cookie_value="1", domain=".google.com", expires=None, email=None):
    cookie = {
        "name": cookie_name,
        "value": cookie_value,
        "domain": domain,
        "path": "/",
    }
    if expires is not None:
        cookie["expires"] = expires
    origins = []
    if email:
        origins = [
            {
                "origin": "https://aistudio.google.com",
                "localStorage": [{"name": "account_email", "value": email}],
            }
        ]
    return {"cookies": [cookie], "origins": origins}


def request_app(app: FastAPI, method: str, url: str, **kwargs) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, url, **kwargs)

    return asyncio.run(send())


def accounts_app(service: AccountService) -> FastAPI:
    app = FastAPI()
    app.include_router(accounts_router)
    app.dependency_overrides[get_account_service] = lambda: service
    return app


def test_account_health_check_marks_valid_account_healthy_and_keeps_tier(tmp_path):
    store = AccountStore(accounts_dir=tmp_path)
    account = store.save_account("main", None, storage_state(email="user@example.com"), tier="pro")

    result = store.test_account_health(account.id)

    refreshed = store.get_account(account.id)
    assert result["ok"] is True
    assert result["status"] == "healthy"
    assert result["tier"] == "pro"
    assert refreshed.email == "user@example.com"
    assert refreshed.health_status == "healthy"
    assert refreshed.is_isolated is False


def test_account_health_check_marks_expired_google_cookie_as_isolated(tmp_path):
    store = AccountStore(accounts_dir=tmp_path)
    expired = datetime(2000, 1, 1, tzinfo=timezone.utc).timestamp()
    account = store.save_account("expired", None, storage_state(expires=expired))

    result = store.test_account_health(account.id)

    refreshed = store.get_account(account.id)
    assert result["ok"] is False
    assert result["status"] == "expired"
    assert "expired" in result["reason"]
    assert refreshed.is_isolated is True


def test_account_health_check_marks_missing_auth_as_isolated(tmp_path):
    store = AccountStore(accounts_dir=tmp_path)
    account = store.save_account("missing", None, storage_state())
    (tmp_path / account.id / "auth.json").unlink()

    result = store.test_account_health(account.id)

    refreshed = store.get_account(account.id)
    assert result["ok"] is False
    assert result["status"] == "missing_auth"
    assert refreshed.is_isolated is True


def test_account_health_route_returns_sanitized_status_payload(tmp_path):
    store = AccountStore(accounts_dir=tmp_path)
    account = store.save_account("main", None, storage_state(cookie_value="synthetic-secret", email="route@example.com"), tier="ultra")
    app = accounts_app(AccountService(store, LoginService()))

    response = request_app(app, "POST", f"/accounts/{account.id}/test")

    body_text = response.text.lower()
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["tier"] == "ultra"
    assert '"cookies"' not in body_text
    assert "synthetic-secret" not in body_text


def test_account_tier_check_can_update_free_account_to_pro(tmp_path):
    store = AccountStore(accounts_dir=tmp_path)
    account = store.save_account("main", None, storage_state(cookie_value="synthetic-secret", email="route@example.com"), tier="free")
    service = AccountService(store, LoginService())

    async def fake_detector(auth_path):
        assert auth_path == tmp_path / account.id / "auth.json"
        return TierResult(tier=AccountTier.PRO, email="route@example.com", raw_header="route@example.com\nPRO")

    result = asyncio.run(service.test_account_with_tier(account.id, tier_detector=fake_detector))

    body_text = json.dumps(result).lower()
    assert result["ok"] is True
    assert result["tier"] == "pro"
    assert store.get_account(account.id).tier == "pro"
    assert '"cookies"' not in body_text
    assert "synthetic-secret" not in body_text


def test_account_update_route_accepts_tier_and_rejects_unknown_tier(tmp_path):
    store = AccountStore(accounts_dir=tmp_path)
    account = store.save_account("main", None, storage_state())
    app = accounts_app(AccountService(store, LoginService()))

    update = request_app(app, "PUT", f"/accounts/{account.id}", json={"tier": "ultra"})
    invalid = request_app(app, "PUT", f"/accounts/{account.id}", json={"tier": "enterprise"})

    assert update.status_code == 200
    assert update.json()["tier"] == "ultra"
    assert store.get_account(account.id).tier == "ultra"
    assert invalid.status_code == 400
    assert "free, pro, ultra" in invalid.json()["detail"]["message"]


def test_rotator_prefers_premium_account_for_image_models(tmp_path):
    store = AccountStore(accounts_dir=tmp_path)
    store.save_account("free", None, storage_state(), tier="free")
    pro = store.save_account("pro", None, storage_state(cookie_name="sid2"), activate=False, tier="pro")
    rotator = AccountRotator(store)

    picked = asyncio.run(rotator.get_next_account("gemini-3.1-flash-image-preview"))

    assert picked.id == pro.id
    assert rotator.last_selection_reason == "image model selected a Pro/Ultra account"


def test_rotator_uses_free_account_for_text_and_logs_image_fallback(tmp_path, caplog):
    store = AccountStore(accounts_dir=tmp_path)
    free = store.save_account("free", None, storage_state(), tier="free")
    rotator = AccountRotator(store)

    text_pick = asyncio.run(rotator.get_next_account("gemini-3-flash-preview"))
    with caplog.at_level(logging.WARNING, logger="aistudio.rotator"):
        image_pick = asyncio.run(rotator.get_next_account("gemini-3.1-flash-image-preview"))

    assert text_pick.id == free.id
    assert image_pick.id == free.id
    assert "fell back" in rotator.last_selection_reason
    assert any("fallback" in record.message.lower() for record in caplog.records)


def test_rotator_rate_limit_and_error_isolation_update_health_and_availability(tmp_path):
    store = AccountStore(accounts_dir=tmp_path)
    limited = store.save_account("limited", None, storage_state(cookie_name="sid1"))
    failing = store.save_account("failing", None, storage_state(cookie_name="sid2"), activate=False)
    healthy = store.save_account("healthy", None, storage_state(cookie_name="sid3"), activate=False)
    rotator = AccountRotator(store, cooldown_seconds=30, error_isolation_threshold=2)

    rotator.record_rate_limited(limited.id)
    rotator.record_error(failing.id)
    rotator.record_error(failing.id)
    picked = asyncio.run(rotator.get_next_account("gemini-3-flash-preview"))
    stats = rotator.get_all_stats()

    assert store.get_account(limited.id).health_status == "rate_limited"
    assert store.get_account(limited.id).is_isolated is True
    assert store.get_account(failing.id).health_status == "isolated"
    assert store.get_account(failing.id).is_isolated is True
    assert stats[limited.id]["is_available"] is False
    assert stats[failing.id]["is_available"] is False
    assert picked.id == healthy.id


def test_lru_selection_prefers_never_used_accounts(tmp_path):
    store = AccountStore(accounts_dir=tmp_path)
    used = store.save_account("used", None, storage_state(cookie_name="sid1"))
    unused = store.save_account("unused", None, storage_state(cookie_name="sid2"), activate=False)
    rotator = AccountRotator(store, mode=RotationMode.LEAST_RECENTLY_USED)
    rotator.record_success(used.id)

    picked = asyncio.run(rotator.get_next_account("gemini-3-flash-preview"))

    assert picked.id == unused.id


def test_exhaustion_selection_keeps_active_account_until_rate_limited(tmp_path):
    store = AccountStore(accounts_dir=tmp_path)
    active = store.save_account("active", None, storage_state(cookie_name="sid1"))
    standby = store.save_account("standby", None, storage_state(cookie_name="sid2"), activate=False)
    rotator = AccountRotator(store, mode=RotationMode.EXHAUSTION, cooldown_seconds=30)

    first = asyncio.run(rotator.get_next_account("gemini-3-flash-preview"))
    second = asyncio.run(rotator.get_next_account("gemini-3-flash-preview"))
    rotator.record_rate_limited(active.id)
    after_limit = asyncio.run(rotator.get_next_account("gemini-3-flash-preview"))

    assert first.id == active.id
    assert second.id == active.id
    assert after_limit.id == standby.id


def test_force_next_can_exclude_active_account_in_exhaustion_mode(tmp_path):
    store = AccountStore(accounts_dir=tmp_path)
    active = store.save_account("active", None, storage_state(cookie_name="sid1"))
    standby = store.save_account("standby", None, storage_state(cookie_name="sid2"), activate=False)
    rotator = AccountRotator(store, mode=RotationMode.EXHAUSTION)

    picked = asyncio.run(rotator.get_next_account(exclude_account_id=active.id))

    assert picked.id == standby.id


def test_account_stats_track_image_usage_by_resolution(tmp_path):
    store = AccountStore(accounts_dir=tmp_path)
    account = store.save_account("main", None, storage_state())
    rotator = AccountRotator(store)

    rotator.record_success(account.id, image_size="1024x1024", image_count=2)
    rotator.record_success(account.id, image_size="1024x1792", image_count=1)
    stats = rotator.get_all_stats()[account.id]

    assert stats["image_sizes"] == {"1024x1024": 2, "1024x1792": 1}
    assert stats["image_total"] == 3


class FakeImageClient:
    def __init__(self):
        self.calls = []

    async def generate_image(self, *, prompt, model, generation_config_overrides=None):
        self.calls.append({"prompt": prompt, "model": model, "generation_config_overrides": generation_config_overrides})
        return ModelOutput(
            candidates=[Candidate(text="ok", images=[GeneratedImage(mime="image/png", data=b"image", size=5)])],
            usage={"total_tokens": 1},
        )


class FakeBrowserSession:
    def __init__(self):
        self.auth_paths = []

    async def switch_auth(self, auth_path):
        self.auth_paths.append(auth_path)


class FakeSnapshotCache:
    def __init__(self):
        self.clear_calls = 0

    def clear(self):
        self.clear_calls += 1


def run_with_account_runtime(coro, *, account_service, rotator, browser_session, snapshot_cache, generated_images_dir=None):
    old_busy_lock = runtime_state.busy_lock
    old_account_service = runtime_state.account_service
    old_rotator = runtime_state.rotator
    old_client = runtime_state.client
    old_snapshot_cache = runtime_state.snapshot_cache
    old_generated_images_dir = settings.generated_images_dir
    old_generated_images_route = settings.generated_images_route
    runtime_state.busy_lock = asyncio.Semaphore(3)
    runtime_state.account_service = account_service
    runtime_state.rotator = rotator
    runtime_state.client = SimpleNamespace(_session=browser_session)
    runtime_state.snapshot_cache = snapshot_cache
    if generated_images_dir is not None:
        settings.generated_images_dir = str(generated_images_dir)
    settings.generated_images_route = "/generated-images"
    try:
        return asyncio.run(coro)
    finally:
        runtime_state.busy_lock = old_busy_lock
        runtime_state.account_service = old_account_service
        runtime_state.rotator = old_rotator
        runtime_state.client = old_client
        runtime_state.snapshot_cache = old_snapshot_cache
        settings.generated_images_dir = old_generated_images_dir
        settings.generated_images_route = old_generated_images_route


def test_image_generation_switches_from_free_active_account_to_available_premium(tmp_path):
    store = AccountStore(accounts_dir=tmp_path)
    free = store.save_account("free", None, storage_state(cookie_name="sid1"), tier="free")
    pro = store.save_account("pro", None, storage_state(cookie_name="sid2"), activate=False, tier="pro")
    account_service = AccountService(store, LoginService())
    rotator = AccountRotator(store)
    browser_session = FakeBrowserSession()
    snapshot_cache = FakeSnapshotCache()
    client = FakeImageClient()

    response = run_with_account_runtime(
        handle_image_generation(ImageRequest(prompt="draw", model="gemini-3.1-flash-image-preview"), client),
        account_service=account_service,
        rotator=rotator,
        browser_session=browser_session,
        snapshot_cache=snapshot_cache,
        generated_images_dir=tmp_path / "generated-images",
    )

    assert store.get_active_account().id == pro.id
    assert store.get_active_account().id != free.id
    assert browser_session.auth_paths == [str(tmp_path / pro.id / "auth.json")]
    assert snapshot_cache.clear_calls == 1
    assert len(client.calls) == 1
    assert response["data"][0]["b64_json"]


def test_image_generation_records_resolution_usage(tmp_path):
    store = AccountStore(accounts_dir=tmp_path)
    pro = store.save_account("pro", None, storage_state(cookie_name="sid1"), tier="pro")
    account_service = AccountService(store, LoginService())
    rotator = AccountRotator(store)
    browser_session = FakeBrowserSession()
    snapshot_cache = FakeSnapshotCache()
    client = FakeImageClient()

    response = run_with_account_runtime(
        handle_image_generation(
            ImageRequest(prompt="draw", model="gemini-3.1-flash-image-preview", size="1024x1024", n=1),
            client,
        ),
        account_service=account_service,
        rotator=rotator,
        browser_session=browser_session,
        snapshot_cache=snapshot_cache,
        generated_images_dir=tmp_path / "generated-images",
    )

    stats = rotator.get_all_stats()[pro.id]
    assert response["data"][0]["b64_json"]
    assert stats["image_sizes"] == {"1024x1024": 1}
    assert stats["image_total"] == 1