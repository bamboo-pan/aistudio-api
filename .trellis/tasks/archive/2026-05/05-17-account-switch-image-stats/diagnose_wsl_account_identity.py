from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from pathlib import Path

from aistudio_api.infrastructure.account.account_store import AccountStore
from aistudio_api.infrastructure.account.tier_detector import TIER_DETECT_JS, _tier_result_from_page_data
from aistudio_api.infrastructure.gateway.client import AIStudioClient


def digest(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.lower().encode("utf-8")).hexdigest()[:10]


def sanitize(text: object) -> str:
    value = str(text)
    value = re.sub(r"/home/bamboo/aistudio-api/data/accounts/[^\s'\"]+", "[REDACTED_ACCOUNT_PATH]", value)
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", value)
    return value


MODEL_TEXT_JS = r"""() => {
    const items = [];
    const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
    for (const el of document.querySelectorAll('button, [role="button"], [role="combobox"], [aria-label], mat-select')) {
        const text = clean(el.innerText || el.textContent);
        const aria = clean(el.getAttribute('aria-label'));
        const combined = `${text} ${aria}`.trim();
        if (!combined) continue;
        if (/gemini|model|pro|image/i.test(combined)) {
            items.push(combined.slice(0, 180));
        }
    }
    return Array.from(new Set(items)).slice(0, 40);
}"""


async def page_identity(client: AIStudioClient) -> dict:
    session = client._session
    if session is None:
        return {"error": "no browser session"}

    def inspect_sync():
        page = session._ensure_hook_page_sync()
        data = page.evaluate(TIER_DETECT_JS)
        result = _tier_result_from_page_data(data)
        model_text = page.evaluate(MODEL_TEXT_JS)
        return {
            "email_hash": digest(result.email),
            "tier": result.tier.value,
            "chat_ready": session._is_chat_runtime_ready_sync(page),
            "url_host": page.url.split("/")[2] if "://" in page.url else page.url[:40],
            "model_text": [sanitize(text) for text in model_text],
        }

    return await session._run_sync(inspect_sync)


async def main() -> int:
    accounts_dir = Path(os.environ.get("AISTUDIO_ACCOUNTS_DIR", "/home/bamboo/aistudio-api/data/accounts"))
    store = AccountStore(accounts_dir=accounts_dir)
    accounts = store.list_accounts()
    client = AIStudioClient(port=int(os.environ.get("AISTUDIO_CAMOUFOX_PORT", "19617")))
    try:
        for account in accounts:
            auth_path = store.get_auth_path(account.id)
            if auth_path is None:
                print("identity_check", {"id": account.id, "auth": False})
                continue
            await client.switch_auth(str(auth_path))
            await client.warmup()
            identity = await page_identity(client)
            expected_hash = digest(account.email)
            print(
                "identity_check",
                json.dumps(
                    {
                        "id": account.id,
                        "registry_tier": account.tier,
                        "registry_email_hash": expected_hash,
                        "page_email_hash": identity.get("email_hash"),
                        "page_tier": identity.get("tier"),
                        "email_matches_registry": expected_hash is not None and expected_hash == identity.get("email_hash"),
                        "chat_ready": identity.get("chat_ready"),
                        "url_host": identity.get("url_host"),
                        "model_text": identity.get("model_text"),
                    },
                    ensure_ascii=False,
                ),
            )
    except Exception as exc:
        print("identity_check_error", exc.__class__.__name__, sanitize(exc)[:1000])
        return 1
    finally:
        if client._session is not None:
            await client._session._run_sync(client._session._close_sync)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))