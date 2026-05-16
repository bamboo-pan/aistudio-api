from __future__ import annotations

import os
import re
from pathlib import Path

from camoufox.sync_api import Camoufox

from aistudio_api.config import settings


EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", re.IGNORECASE)


def main() -> None:
    accounts_dir = Path(os.environ.get("AISTUDIO_ACCOUNTS_DIR", "/home/bamboo/aistudio-api/data/accounts"))
    auth_files = sorted(accounts_dir.glob("*/auth.json"))
    if not auth_files:
        raise SystemExit("No auth.json files found")

    options = {"headless": settings.camoufox_headless, "main_world_eval": True}
    if settings.proxy_server:
        options["proxy"] = {"server": settings.proxy_server}

    with Camoufox(**options) as browser:
        ctx = browser.new_context(storage_state=str(auth_files[0]))
        try:
            page = ctx.new_page()
            page.goto("https://aistudio.google.com/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_function(
                "() => document.body && document.body.innerText && document.body.innerText.length > 0",
                timeout=60000,
            )
            page.wait_for_timeout(3000)
            data = page.evaluate(
                r"""() => {
                    const emailRe = /[\w.+-]+@[\w.-]+\.[a-z]{2,}/ig;
                    const sanitize = value => String(value || '')
                        .replace(emailRe, '<email>')
                        .replace(/\s+/g, ' ')
                        .trim();
                    const collect = selector => Array.from(document.querySelectorAll(selector))
                        .map(el => sanitize(el.innerText || el.textContent))
                        .filter(Boolean)
                        .slice(0, 80);
                    const lines = String(document.body.innerText || '')
                        .split(/\n+/)
                        .map(sanitize)
                        .filter(Boolean);
                    const hits = lines
                        .filter(line => /\b(pro|ultra|upgrade|member|membership|plan|google ai|free|advanced)\b/i.test(line))
                        .slice(0, 80);
                    return {
                        url: location.href,
                        title: document.title,
                        bodyLength: document.body.innerText.length,
                        header: collect('header, [role="banner"], nav'),
                        buttons: collect('button, [role="button"]'),
                        hits,
                    };
                }"""
            )
            try:
                page.get_by_text(EMAIL_RE.sub("<email>", "placeholder@example.com"), exact=False)
            except Exception:
                pass
            account_button = page.locator("button").filter(has_text=re.compile(r"@", re.IGNORECASE)).first
            try:
                account_button.click(timeout=5000)
                page.wait_for_timeout(2000)
            except Exception:
                pass
            menu_data = page.evaluate(
                r"""() => {
                    const emailRe = /[\w.+-]+@[\w.-]+\.[a-z]{2,}/ig;
                    const sanitize = value => String(value || '')
                        .replace(emailRe, '<email>')
                        .replace(/\s+/g, ' ')
                        .trim();
                    const lines = String(document.body.innerText || '')
                        .split(/\n+/)
                        .map(sanitize)
                        .filter(Boolean);
                    const hits = lines
                        .filter(line => /\b(pro|ultra|upgrade|member|membership|plan|google ai|free|advanced|premium|storage|benefits)\b/i.test(line))
                        .slice(0, 120);
                    const overlays = Array.from(document.querySelectorAll('[role="dialog"], [role="menu"], .cdk-overlay-pane, iframe'))
                        .map(el => sanitize(el.innerText || el.textContent || el.getAttribute('title') || el.getAttribute('aria-label')))
                        .filter(Boolean)
                        .slice(0, 40);
                    return {hits, overlays, bodyLength: document.body.innerText.length};
                }"""
            )
            print(data)
            print({"after_account_click": menu_data})
        finally:
            ctx.close()


if __name__ == "__main__":
    main()