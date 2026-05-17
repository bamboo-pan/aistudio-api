from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

from aistudio_api.infrastructure.account.account_store import AccountStore
from aistudio_api.infrastructure.gateway.client import AIStudioClient


COLLECT_MODEL_TEXT_JS = r"""() => {
    const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
    const items = [];
    for (const el of document.querySelectorAll('button, [role="button"], [role="option"], [role="combobox"], [aria-label], mat-select, mat-option, a')) {
        const text = clean(el.innerText || el.textContent);
        const aria = clean(el.getAttribute('aria-label'));
        const combined = `${text} ${aria}`.trim();
        if (!combined) continue;
        if (/gemini|image|imagen|model|nano|banana|pro/i.test(combined)) {
            items.push(combined.slice(0, 220));
        }
    }
    return Array.from(new Set(items)).slice(0, 80);
}"""

CONSENT_DEBUG_JS = r"""() => {
    const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
    const visible = (el) => {
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        return {visible: rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none', rect: [Math.round(rect.x), Math.round(rect.y), Math.round(rect.width), Math.round(rect.height)]};
    };
    const checkboxCandidates = Array.from(document.querySelectorAll('mat-checkbox, [role="checkbox"], label, input[type="checkbox"], .mdc-checkbox, .mat-mdc-checkbox')).map((el) => {
        const input = el.matches && el.matches('input[type="checkbox"]') ? el : el.querySelector && el.querySelector('input[type="checkbox"]');
        return {tag: el.tagName, role: el.getAttribute('role'), text: clean(el.innerText || el.textContent || el.getAttribute('aria-label')).slice(0, 220), ariaChecked: el.getAttribute('aria-checked'), inputChecked: input ? input.checked : null, ...visible(el)};
    }).slice(0, 30);
    const buttons = Array.from(document.querySelectorAll('button, [role="button"]')).map((el) => ({tag: el.tagName, text: clean(el.innerText || el.textContent || el.getAttribute('aria-label')).slice(0, 160), disabled: el.disabled || el.getAttribute('aria-disabled'), ...visible(el)})).slice(0, 50);
    return {checkboxCandidates, buttons};
}"""

CLICK_BUTTON_TEXT_JS = r"""(needle) => {
    const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
    const visible = (el) => {
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
    };
    const lowerNeedle = String(needle || '').toLowerCase();
    for (const button of Array.from(document.querySelectorAll('button, [role="button"]'))) {
        if (!visible(button)) continue;
        const label = clean(button.innerText || button.textContent || button.getAttribute('aria-label'));
        if (label.toLowerCase().includes(lowerNeedle)) {
            button.click();
            return {clicked: true, label: label.slice(0, 180)};
        }
    }
    return {clicked: false};
}"""


def sanitize(value: object) -> str:
    text = str(value)
    text = re.sub(r"/home/bamboo/aistudio-api/data/accounts/[^\s'\"]+", "[REDACTED_ACCOUNT_PATH]", text)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", text)
    return text


async def main() -> int:
    accounts_dir = Path(os.environ.get("AISTUDIO_ACCOUNTS_DIR", "/home/bamboo/aistudio-api/data/accounts"))
    account_id = os.environ.get("AISTUDIO_DIAG_ACCOUNT_ID", "acc_180b3249")
    store = AccountStore(accounts_dir=accounts_dir)
    auth_path = store.get_auth_path(account_id)
    if auth_path is None:
        print("selector_error", "auth missing")
        return 1

    client = AIStudioClient(port=int(os.environ.get("AISTUDIO_CAMOUFOX_PORT", "19619")))
    try:
        await client.switch_auth(str(auth_path))
        await client.warmup()
        session = client._session
        assert session is not None

        def inspect_sync():
            page = session._ensure_hook_page_sync()

            def collect(label: str):
                print("selector_text", label, json.dumps([sanitize(item) for item in page.evaluate(COLLECT_MODEL_TEXT_JS)], ensure_ascii=False))
                print("consent_debug", label, json.dumps(page.evaluate(CONSENT_DEBUG_JS), ensure_ascii=False))

            def click_text(label: str) -> bool:
                try:
                    result = page.evaluate(CLICK_BUTTON_TEXT_JS, label)
                    page.wait_for_timeout(2000)
                    print("selector_click_result", label, json.dumps(result, ensure_ascii=False))
                    return bool(result.get("clicked")) if isinstance(result, dict) else False
                except Exception as exc:
                    print("selector_click_error", label, exc.__class__.__name__, sanitize(exc)[:300])
                    return False

            collect("initial")
            print("clicked_image_generation", click_text("Image Generation"))
            collect("after_image_generation")
            print("clicked_pro_image", click_text("Gemini 3 Pro Image"))
            collect("after_pro_image")
            print("clicked_nano", click_text("Nano Banana"))
            collect("after_nano")

        await session._run_sync(inspect_sync)
        return 0
    except Exception as exc:
        print("selector_error", exc.__class__.__name__, sanitize(exc)[:1000])
        return 1
    finally:
        if client._session is not None:
            await client._session._run_sync(client._session._close_sync)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))