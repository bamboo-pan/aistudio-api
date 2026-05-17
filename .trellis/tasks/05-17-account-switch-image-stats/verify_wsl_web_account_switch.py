from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from verify_wsl_account_switch_api import (  # noqa: E402
    ACCOUNTS_DIR,
    SRC,
    HttpClient,
    copy_repo,
    drain_recent_logs,
    make_env,
    request_json,
    run,
    sanitize,
    start_log_reader,
    wait_for_server,
)


def restore_accounts(client: HttpClient) -> list[dict[str, Any]]:
    status, accounts = request_json(client, "GET", "/accounts")
    if status != 200 or not isinstance(accounts, list):
        raise AssertionError(f"accounts request failed: {status}")

    for account in accounts:
        update_status, updated = request_json(client, "PUT", f"/accounts/{account['id']}", json={"tier": "pro"})
        print("web_account_tier_restore", {"id": account.get("id"), "status": update_status, "tier": updated.get("tier")})
        if update_status != 200 or updated.get("tier") != "pro":
            raise AssertionError(f"failed to restore Pro tier for {account.get('id')}: {update_status}")

    status, accounts = request_json(client, "GET", "/accounts")
    premium = [account for account in accounts if account.get("tier") in {"pro", "ultra"}]
    print("web_premium_accounts", [{"id": account.get("id"), "tier": account.get("tier"), "health": account.get("health_status")} for account in premium])
    if len(premium) < 2:
        raise AssertionError(f"expected at least two Pro/Ultra accounts, got {len(premium)}")
    return premium[:2]


def frontend_state(page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
            const app = window.__aistudioApp && window.__aistudioApp();
            if (!app) return {ready: false};
            return {
                ready: true,
                view: app.view,
                activeId: app.activeId,
                imageModel: app.imageModel,
                imageError: app.imageError,
                imageBusy: app.imageBusy,
                imageResults: (app.imageResults || []).length,
                statsTotals: app.statsTotals || {},
                totalAccountRequests: app.totalAccountRequests,
                totalAccountImageUsage: app.totalAccountImageUsage,
                accountRows: (app.accountRows || []).map((account) => ({
                    id: account.id,
                    requests: account.requests || 0,
                    success: account.success || 0,
                    errors: account.errors || 0,
                    image_total: account.image_total || 0,
                    health_status: account.health_status,
                })),
            };
        }"""
    )


def assert_frontend_stats(page, expected_requests: int, expected_success: int) -> None:
    state = frontend_state(page)
    print(
        "web_frontend_state",
        {
            "activeId": state.get("activeId"),
            "imageResults": state.get("imageResults"),
            "modelRequests": state.get("statsTotals", {}).get("requests"),
            "accountRequests": state.get("totalAccountRequests"),
        },
    )
    if state.get("statsTotals", {}).get("requests") != expected_requests:
        raise AssertionError(f"frontend model request total mismatch: {state}")
    if state.get("statsTotals", {}).get("success") != expected_success:
        raise AssertionError(f"frontend model success total mismatch: {state}")
    if state.get("totalAccountRequests") != expected_requests:
        raise AssertionError(f"frontend account request total mismatch: {state}")
    if sum(row.get("success", 0) for row in state.get("accountRows", [])) != expected_success:
        raise AssertionError(f"frontend account success total mismatch: {state}")


def assert_backend_stats(client: HttpClient, expected_requests: int, expected_success: int) -> None:
    stats_status, stats = request_json(client, "GET", "/stats")
    rotation_status, rotation = request_json(client, "GET", "/rotation")
    if stats_status != 200 or rotation_status != 200:
        raise AssertionError(f"backend stats endpoints failed: stats={stats_status} rotation={rotation_status}")
    totals = stats.get("totals", {})
    account_stats = rotation.get("accounts", {})
    account_requests = sum(value.get("requests", 0) for value in account_stats.values())
    account_success = sum(value.get("success", 0) for value in account_stats.values())
    print("web_backend_stats", {"model_requests": totals.get("requests"), "account_requests": account_requests})
    if totals.get("requests") != expected_requests or account_requests != expected_requests:
        raise AssertionError(f"backend request totals mismatch: model={totals.get('requests')} account={account_requests}")
    if totals.get("success") != expected_success or account_success != expected_success:
        raise AssertionError(f"backend success totals mismatch: model={totals.get('success')} account={account_success}")


def drive_web_generation(page, *, account_id: str, prompt: str, model: str, size: str = "1024x1024") -> dict[str, Any]:
    return page.evaluate(
        """async ({accountId, prompt, model, size}) => {
            const app = window.__aistudioApp();
            app.go('accounts');
            await app.activateAccount(accountId);
            app.go('images');
            await app.loadModels();
            app.selectImageModel(model);
            if ((app.imageSizeValues || []).includes(size)) app.imageSize = size;
            app.imageCount = 1;
            app.imagePrompt = prompt;
            app.imageError = '';
            await app.generateImage();
            return {
                activeId: app.activeId,
                imageModel: app.imageModel,
                imageError: app.imageError,
                imageResults: (app.imageResults || []).length,
                statsTotals: app.statsTotals || {},
                totalAccountRequests: app.totalAccountRequests,
            };
        }""",
        {"accountId": account_id, "prompt": prompt, "model": model, "size": size},
    )


def web_flow(base_url: str) -> None:
    client = HttpClient(base_url)
    first, second = restore_accounts(client)

    from camoufox.sync_api import Camoufox

    with Camoufox(headless=True, main_world_eval=True) as browser:
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(420_000)
        page.goto(f"{base_url}/#accounts", wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            """async () => {
                const findAppFactory = () => {
                    if (typeof window.app === 'function') return window.app;
                    try { if (typeof app === 'function') return app; } catch (e) {}
                    return null;
                };
                let appFactory = findAppFactory();
                if (!appFactory) {
                    const source = await fetch('/static/app.js').then((response) => response.text());
                    appFactory = Function(`${source}\nreturn typeof app === 'function' ? app : (typeof window.app === 'function' ? window.app : null);`)();
                }
                if (!appFactory) throw new Error('frontend app factory not found');
                window.__aistudioTestApp = appFactory();
                window.__aistudioApp = () => {
                    if (window.__aistudioTestApp) return window.__aistudioTestApp;
                    const nodes = [document.body, ...document.querySelectorAll('*')];
                    if (window.Alpine && typeof window.Alpine.$data === 'function') {
                        for (const node of nodes) {
                            try {
                                const data = window.Alpine.$data(node);
                                if (data && typeof data.generateImage === 'function') return data;
                            } catch (e) {}
                        }
                    }
                    for (const node of nodes) {
                        const stack = node && node._x_dataStack;
                        if (stack && stack[0] && typeof stack[0].generateImage === 'function') return stack[0];
                        const legacy = node && node.__x && node.__x.$data;
                        if (legacy && typeof legacy.generateImage === 'function') return legacy;
                    }
                    const appFactory = typeof window.app === 'function'
                        ? window.app
                        : (typeof app === 'function' ? app : null);
                    if (appFactory) {
                        window.__aistudioTestApp = appFactory();
                        return window.__aistudioTestApp;
                    }
                    return null;
                };
            }"""
        )
        page.wait_for_function("() => !!(window.__aistudioApp && window.__aistudioApp())", timeout=120_000)
        page.evaluate(
            """async () => {
                const app = window.__aistudioApp();
                await Promise.all([app.loadModels(), app.loadAccounts(), app.loadStats(), app.loadRotation(), app.loadImageSessions(false)]);
                app.ensureImageDefaults();
            }"""
        )
        page.wait_for_function("() => { const app = window.__aistudioApp(); return app && app.models.length > 0 && app.accounts.length >= 2; }", timeout=120_000)

        expected_requests = 0
        expected_success = 0
        for account, color in ((first, "yellow"), (second, "purple")):
            result = drive_web_generation(
                page,
                account_id=account["id"],
                model="gemini-3-pro-image-preview",
                prompt=f"Web verification on account {account['id']}: a small {color} cube on white background, no text.",
            )
            print("web_image_result", {"account": account["id"], "results": result.get("imageResults"), "error": result.get("imageError")})
            if result.get("imageError"):
                raise AssertionError(f"web image generation failed for {account['id']}: {sanitize(result.get('imageError'))}")
            if result.get("imageResults") != 1:
                raise AssertionError(f"web image generation returned unexpected result count: {result}")
            expected_requests += 1
            expected_success += 1
            assert_frontend_stats(page, expected_requests, expected_success)
            assert_backend_stats(client, expected_requests, expected_success)

        context.close()

    print("web_account_switch_flow_ok", True)
    print("live_secrets_printed", False)


def run_browser_flow_in_venv(venv_python: Path, base_url: str) -> None:
    result = run(
        [str(venv_python), str(Path(__file__).resolve()), "--browser-flow", base_url],
        timeout=1200,
        allow_fail=True,
    )
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, result.args, output=result.stdout)


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--browser-flow":
        web_flow(sys.argv[2])
        return 0

    tmp = Path(tempfile.mkdtemp(prefix="aistudio-api-u2-web-switch-", dir="/home/bamboo"))
    print("temp_dir", tmp)
    copy_repo(SRC, tmp)

    venv_python = tmp / ".venv" / "bin" / "python"
    run(["python3", "-m", "venv", ".venv"], cwd=tmp, timeout=300)
    run([str(venv_python), "-m", "pip", "install", "-q", "--upgrade", "pip"], cwd=tmp, timeout=600)
    run([str(venv_python), "-m", "pip", "install", "-q", "-e", ".[test]"], cwd=tmp, timeout=900)
    camoufox_fetch = run([str(venv_python), "-m", "camoufox", "fetch"], cwd=tmp, timeout=900, allow_fail=True)
    print("camoufox_fetch_ok", camoufox_fetch.returncode == 0)

    env = make_env(tmp)
    env["AISTUDIO_CAMOUFOX_PORT"] = "19527"
    env["AISTUDIO_LOGIN_CAMOUFOX_PORT"] = "19528"
    base_url = "http://127.0.0.1:18527"
    server = subprocess.Popen(
        [
            str(venv_python),
            "-c",
            "from aistudio_api.main import main; main()",
            "server",
            "--port",
            "18527",
            "--camoufox-port",
            "19527",
        ],
        cwd=tmp,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    log_lines, _ = start_log_reader(server)
    try:
        wait_for_server(base_url)
        run_browser_flow_in_venv(venv_python, base_url)
        return 0
    except Exception as exc:
        print("web_account_switch_flow_ok", False)
        print("failure_type", exc.__class__.__name__)
        print("failure", sanitize(exc)[:1200])
        recent = drain_recent_logs(log_lines)
        if recent:
            print("recent_server_logs_begin")
            for line in recent:
                print(line)
            print("recent_server_logs_end")
        return 1
    finally:
        server.terminate()
        try:
            server.wait(timeout=30)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())