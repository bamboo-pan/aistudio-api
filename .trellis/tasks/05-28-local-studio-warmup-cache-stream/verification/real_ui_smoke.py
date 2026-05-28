import asyncio
import json
import time
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:8093"
OPENAI_KEY_PATH = Path("/mnt/c/Users/bamboo/Documents/github/key.txt")
ARTIFACTS = Path("/home/bamboo/aistudio-api-u1-realtest/artifacts")
ARTIFACTS.mkdir(parents=True, exist_ok=True)
RUN_ID = f"ui-stream-cache-{int(time.time())}"


def fail(message, details=None):
    payload = {"ok": False, "message": message, "details": details or {}}
    (ARTIFACTS / "ui_smoke_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    raise SystemExit(message)


def read_openai_credentials():
    lines = [line.strip() for line in OPENAI_KEY_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    base_url = "https://api.openai.com/v1"
    token = ""
    for line in lines:
        if line.startswith(("http://", "https://")):
            base_url = line.rstrip("/")
        elif "=" in line:
            key, value = line.split("=", 1)
            lowered = key.strip().lower()
            if lowered in {"base_url", "api_base", "openai_base_url"}:
                base_url = value.strip().rstrip("/")
            elif lowered in {"api_key", "token", "openai_api_key"}:
                token = value.strip()
        elif not token:
            token = line
    if not token:
        fail("OpenAI-compatible key file did not contain a token")
    return base_url, token


def request_json(client, method, path, **kwargs):
    response = client.request(method, BASE_URL + path, **kwargs)
    if response.status_code >= 400:
        fail(f"{method} {path} failed", {"status": response.status_code, "body_prefix": response.text[:500].replace("\n", " ")})
    return response.json(), response


def fetch_recent_groups(client, limit=60):
    data, _ = request_json(client, "GET", f"/request-logs?limit={limit}")
    groups = []
    for item in data.get("data", []):
        group, _ = request_json(client, "GET", f"/request-logs/groups/{item['id']}")
        groups.append(group)
    return groups


def group_contains(group, text):
    return text in json.dumps(group, ensure_ascii=False)


def group_phases(group):
    return [entry.get("phase") for entry in group.get("entries", [])]


def assert_no_secret(groups, token):
    for group in groups:
        if token and token in json.dumps(group, ensure_ascii=False):
            fail("Request logs leaked the OpenAI-compatible token", {"group": group.get("id")})


async def app_data(page):
    return await page.evaluate("() => document.body._x_dataStack && document.body._x_dataStack[0] ? true : false")


async def configure_local_studio(page, base_url, token):
    await page.goto(BASE_URL + "/#studio", wait_until="networkidle")
    await page.wait_for_function("() => document.body._x_dataStack && document.body._x_dataStack[0]")
    body_text = await page.locator("body").inner_text()
    if "Cache Namespace" in body_text or "localStudioCache" in body_text:
        fail("Local Studio UI still exposes cache namespace/cache state")
    models = await page.evaluate(
        """async ({baseUrl, token}) => {
            const app = document.body._x_dataStack[0];
            const provider = {id:'ui-smoke-openai', type:'openai', providerType:'openai', name:'UI Smoke OpenAI', baseUrl, apiKey:token, timeout:180, interfaceMode:'responses'};
            app.localStudioProviders = [provider];
            app.localStudioProviderId = provider.id;
            app.localStudioProviderType = 'openai';
            app.localStudioSettings = {name:provider.name, baseUrl, apiKey:token, timeout:180};
            app.localStudioInterfaceMode = 'responses';
            app.localStudioStream = 'on';
            app.localStudioSearch = 'off';
            app.localStudioReasoningEffort = 'off';
            app.localStudioImageToolEnabled = false;
            app.localStudioConversation = null;
            app.localStudioConversations = [];
            app.saveLocalStudioSettings();
            await app.loadLocalStudioModels();
            const ids = (app.localStudioModelOptions || []).map((model) => model.id);
            const preferred = ['gpt-4.1-mini','gpt-4o-mini','gpt-4.1-nano','o4-mini','gpt-4o'];
            app.localStudioModel = preferred.find((id) => ids.includes(id)) || ids.find((id) => !/image|audio|embedding/i.test(id)) || ids[0] || '';
            app.saveLocalStudioSettings();
            return {ids, selected: app.localStudioModel};
        }""",
        {"baseUrl": base_url, "token": token},
    )
    if not models.get("selected"):
        fail("UI could not load/select a Local Studio model", {"model_count": len(models.get("ids") or [])})
    await page.wait_for_function("() => !!document.body._x_dataStack[0].localStudioModel")
    return models["selected"]


async def send_prompt_and_watch_stream(page, prompt):
    baseline_count = await page.evaluate("() => (document.body._x_dataStack[0].localStudioActiveMessages || []).length")
    textarea = page.locator("textarea[placeholder^='向 Local Studio']")
    await textarea.fill(prompt)
    await page.locator(".local-studio-compose-row button.send").click()
    await page.wait_for_function("() => document.body._x_dataStack[0].localStudioBusy === true")
    started = time.perf_counter()
    first_visible_seconds = None
    visible_during_busy = False
    max_len_during_busy = 0
    snapshots = []
    while True:
        state = await page.evaluate(
            """(baselineCount) => {
                const app = document.body._x_dataStack[0];
                const messages = app.localStudioActiveMessages || [];
                const assistant = messages.slice(baselineCount).find((message) => message.role === 'assistant') || {};
                return {busy: app.localStudioBusy, content: assistant.content || '', error: app.localStudioError || assistant.error || ''};
            }""",
            baseline_count,
        )
        if state["error"]:
            fail("UI stream showed an error", {"error": state["error"][:300]})
        content_len = len(state["content"])
        if state["busy"] and content_len > 0:
            visible_during_busy = True
            max_len_during_busy = max(max_len_during_busy, content_len)
            if first_visible_seconds is None:
                first_visible_seconds = time.perf_counter() - started
            snapshots.append(content_len)
        if not state["busy"]:
            final_content = state["content"]
            break
        if time.perf_counter() - started > 180:
            fail("UI stream did not finish in time")
        await page.wait_for_timeout(250)
    if not final_content.strip():
        fail("UI final assistant content was empty")
    if not visible_during_busy:
        fail("UI did not show stream content until after completion")
    if first_visible_seconds is not None and first_visible_seconds > 35:
        fail("UI stream first visible content was too slow", {"first_visible_seconds": round(first_visible_seconds, 3)})
    return {"first_visible_seconds": round(first_visible_seconds or 0, 3), "max_len_during_busy": max_len_during_busy, "sample_count": len(snapshots), "final_len": len(final_content)}


async def main():
    base_url, token = read_openai_credentials()
    summary = {"ok": True, "run_id": RUN_ID}
    with httpx.Client(timeout=60) as client:
        request_json(client, "PUT", "/request-logs/status", json={"enabled": True})
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        try:
            selected = await configure_local_studio(page, base_url, token)
            summary["selected_model"] = selected
            prompt = f"For UI streaming test {RUN_ID}, write the numbers 1 through 80, one number per line, with no extra prose."
            summary["first_send"] = await send_prompt_and_watch_stream(page, prompt)
            summary["second_send"] = await send_prompt_and_watch_stream(page, prompt)
            await page.screenshot(path=str(ARTIFACTS / "ui_smoke.png"), full_page=True)
        finally:
            await browser.close()
    with httpx.Client(timeout=60) as client:
        groups = [group for group in fetch_recent_groups(client) if group_contains(group, RUN_ID)]
        upstream_groups = [group for group in groups if "upstream_request" in group_phases(group)]
        assert_no_secret(groups, token)
        if len(upstream_groups) < 2:
            fail("UI repeated prompt did not create two upstream request groups", {"matching_groups": len(groups), "upstream_groups": len(upstream_groups)})
        summary["matching_request_log_groups"] = len(groups)
        summary["upstream_request_groups"] = len(upstream_groups)
    (ARTIFACTS / "ui_smoke_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
