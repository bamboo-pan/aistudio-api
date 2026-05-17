from __future__ import annotations

import os
import queue
import re
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


SRC = Path("/mnt/c/Users/bamboo/Desktop/aistudio-api_u2")
ACCOUNTS_DIR = Path("/home/bamboo/aistudio-api/data/accounts")
DEFAULT_WSL_PROXY = "http://192.168.128.1:7890"
EXCLUDED_DIRS = {".git", ".venv", "data", "__pycache__", ".pytest_cache"}


def sanitize(text: Any) -> str:
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


def make_env(tmp: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["AISTUDIO_ACCOUNTS_DIR"] = str(ACCOUNTS_DIR)
    env["AISTUDIO_CAMOUFOX_HEADLESS"] = "1"
    env["AISTUDIO_CAMOUFOX_PORT"] = "19517"
    env["AISTUDIO_LOGIN_CAMOUFOX_PORT"] = "19518"
    env["AISTUDIO_TIMEOUT_CAPTURE"] = "120"
    env["AISTUDIO_TIMEOUT_REPLAY"] = "300"
    env["AISTUDIO_TIMEOUT_STREAM"] = "180"
    env["AISTUDIO_DUMP_RAW_RESPONSE"] = "0"
    env["AISTUDIO_GENERATED_IMAGES_DIR"] = str(tmp / "runtime-data" / "generated-images")
    env["AISTUDIO_IMAGE_SESSIONS_DIR"] = str(tmp / "runtime-data" / "image-sessions")
    env["AISTUDIO_ACCOUNT_ROTATION_MODE"] = "round_robin"
    proxy_server = env.get("AISTUDIO_PROXY_SERVER") or DEFAULT_WSL_PROXY
    env["AISTUDIO_PROXY_SERVER"] = proxy_server
    env.setdefault("HTTPS_PROXY", proxy_server)
    env.setdefault("HTTP_PROXY", proxy_server)
    return env


def start_log_reader(process: subprocess.Popen[str]) -> tuple[queue.Queue[str], threading.Thread]:
    lines: queue.Queue[str] = queue.Queue()

    def read_logs() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            safe = sanitize(line.rstrip())
            lines.put(safe)
            print(safe)

    thread = threading.Thread(target=read_logs, daemon=True)
    thread.start()
    return lines, thread


def drain_recent_logs(lines: queue.Queue[str], limit: int = 80) -> list[str]:
    drained: list[str] = []
    while True:
        try:
            drained.append(lines.get_nowait())
        except queue.Empty:
            break
    return drained[-limit:]


def wait_for_server(base_url: str, timeout: int = 180) -> None:
    deadline = time.time() + timeout
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=5) as response:
                if response.status == 200:
                    return
                last_error = f"status={response.status}"
        except Exception as exc:
            last_error = f"{exc.__class__.__name__}: {exc}"
        time.sleep(2)
    raise RuntimeError(f"server did not become ready: {sanitize(last_error)}")


class HttpClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, *, json_body: dict[str, Any] | None = None, timeout: int = 420) -> tuple[int, str]:
        url = path if path.startswith("http://") or path.startswith("https://") else f"{self.base_url}{path}"
        data = None
        headers: dict[str, str] = {}
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", errors="replace")


def request_json(client: HttpClient, method: str, path: str, **kwargs: Any) -> tuple[int, dict[str, Any]]:
    status, text = client.request(method, path, json_body=kwargs.get("json"))
    try:
        body = json.loads(text) if text else {}
    except Exception:
        body = {"raw": text[:1000]}
    return status, body


def error_message(body: dict[str, Any]) -> str:
    error = body.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error)
    detail = body.get("detail")
    if isinstance(detail, dict):
        return str(detail.get("message") or detail)
    return str(body)[:1000]


def visible_account(account: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": account.get("id"),
        "tier": account.get("tier"),
        "health_status": account.get("health_status"),
    }


def assert_stats_consistent(client: HttpClient, expected_requests: int, expected_success: int) -> None:
    stats_status, stats = request_json(client, "GET", "/stats")
    rotation_status, rotation = request_json(client, "GET", "/rotation")
    if stats_status != 200 or rotation_status != 200:
        raise AssertionError(f"stats endpoints failed: stats={stats_status} rotation={rotation_status}")
    totals = stats.get("totals", {})
    account_stats = rotation.get("accounts", {})
    account_requests = sum(value.get("requests", 0) for value in account_stats.values())
    account_success = sum(value.get("success", 0) for value in account_stats.values())
    print("stats_totals", {"requests": totals.get("requests"), "success": totals.get("success"), "errors": totals.get("errors")})
    print("account_totals", {"requests": account_requests, "success": account_success})
    if totals.get("requests") != expected_requests or account_requests != expected_requests:
        raise AssertionError(f"request totals mismatch: model={totals.get('requests')} account={account_requests} expected={expected_requests}")
    if totals.get("success") != expected_success or account_success != expected_success:
        raise AssertionError(f"success totals mismatch: model={totals.get('success')} account={account_success} expected={expected_success}")


def generate_image(
    client: HttpClient,
    *,
    account_id: str,
    model: str,
    size: str,
    response_format: str,
    prompt: str,
) -> None:
    activate_status, active = request_json(client, "POST", f"/accounts/{account_id}/activate")
    print("activate", {"account": account_id, "status": activate_status})
    if activate_status != 200 or active.get("id") != account_id:
        raise AssertionError(f"activation failed for {account_id}: {activate_status} {sanitize(active)}")

    image_status, image_body = request_json(
        client,
        "POST",
        "/v1/images/generations",
        json={
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": 1,
            "response_format": response_format,
        },
    )
    print("image_result", {"account": account_id, "model": model, "size": size, "status": image_status})
    if image_status != 200:
        print("image_error", sanitize(error_message(image_body))[:1000])
        raise AssertionError(f"image generation failed for {account_id} on {model}: {image_status}")

    items = image_body.get("data") or []
    if not items:
        raise AssertionError("image generation returned no data")
    first = items[0]
    if response_format == "url":
        url = str(first.get("url") or "")
        if not url:
            raise AssertionError("URL image response omitted url")
        fetch_status, _ = request_json(client, "GET", url)
        print("generated_image_fetch", {"status": fetch_status, "url_prefix": url[:32]})
        if fetch_status not in (200, 304):
            raise AssertionError(f"generated image URL did not fetch: {fetch_status}")
    else:
        b64_len = len(str(first.get("b64_json") or ""))
        print("generated_image_b64_len", b64_len)
        if b64_len <= 100:
            raise AssertionError("b64 image response too small")


def api_flow(base_url: str) -> None:
    client = HttpClient(base_url)
    if True:
        status, accounts = request_json(client, "GET", "/accounts")
        if status != 200 or not isinstance(accounts, list):
            raise AssertionError(f"accounts request failed: {status}")
        print("accounts_initial", [visible_account(account) for account in accounts])

        for account in accounts:
            update_status, updated = request_json(client, "PUT", f"/accounts/{account['id']}", json={"tier": "pro"})
            print("account_tier_restore", {"id": account.get("id"), "status": update_status, "tier": updated.get("tier")})
            if update_status != 200 or updated.get("tier") != "pro":
                raise AssertionError(f"failed to restore Pro tier for {account.get('id')}: {update_status} {sanitize(updated)}")

        refreshed: list[dict[str, Any]] = []
        for account in accounts:
            test_status, result = request_json(client, "POST", f"/accounts/{account['id']}/test")
            refreshed_account = result.get("account", {}) if isinstance(result, dict) else {}
            refreshed.append(refreshed_account)
            print("account_test", {"id": account.get("id"), "status": test_status, "ok": result.get("ok"), "tier": result.get("tier")})
            if test_status != 200 or not result.get("ok"):
                raise AssertionError(f"account health test failed for {account.get('id')}: {test_status} {sanitize(result)}")

        status, accounts = request_json(client, "GET", "/accounts")
        premium = [account for account in accounts if account.get("tier") in {"pro", "ultra"}]
        print("premium_accounts", [visible_account(account) for account in premium])
        if len(premium) < 2:
            raise AssertionError(f"expected at least two Pro/Ultra accounts, got {len(premium)}")

        first, second = premium[0], premium[1]
        expected_requests = 0
        expected_success = 0

        generate_image(
            client,
            account_id=first["id"],
            model="gemini-3-pro-image-preview",
            size="1024x1024",
            response_format="url",
            prompt="API verification image on first Pro account: a small red cube on a white background, no text.",
        )
        expected_requests += 1
        expected_success += 1
        assert_stats_consistent(client, expected_requests, expected_success)

        generate_image(
            client,
            account_id=second["id"],
            model="gemini-3-pro-image-preview",
            size="1024x1024",
            response_format="url",
            prompt="API verification image on second Pro account: a small green cube on a white background, no text.",
        )
        expected_requests += 1
        expected_success += 1
        assert_stats_consistent(client, expected_requests, expected_success)

        generate_image(
            client,
            account_id=first["id"],
            model="gemini-3.1-flash-image-preview",
            size="512x512",
            response_format="b64_json",
            prompt="API verification switch back to first account: a small blue square on white, no text.",
        )
        expected_requests += 1
        expected_success += 1
        assert_stats_consistent(client, expected_requests, expected_success)

        print("api_account_switch_flow_ok", True)
        print("live_secrets_printed", False)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="aistudio-api-u2-account-switch-", dir="/home/bamboo"))
    print("temp_dir", tmp)
    copy_repo(SRC, tmp)

    venv_python = tmp / ".venv" / "bin" / "python"
    run(["python3", "-m", "venv", ".venv"], cwd=tmp, timeout=300)
    run([str(venv_python), "-m", "pip", "install", "-q", "--upgrade", "pip"], cwd=tmp, timeout=600)
    run([str(venv_python), "-m", "pip", "install", "-q", "-e", ".[test]"], cwd=tmp, timeout=900)

    camoufox_fetch = run([str(venv_python), "-m", "camoufox", "fetch"], cwd=tmp, timeout=900, allow_fail=True)
    print("camoufox_fetch_ok", camoufox_fetch.returncode == 0)

    env = make_env(tmp)
    base_url = "http://127.0.0.1:18517"
    server = subprocess.Popen(
        [
            str(venv_python),
            "-c",
            "from aistudio_api.main import main; main()",
            "server",
            "--port",
            "18517",
            "--camoufox-port",
            "19517",
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
        api_flow(base_url)
        return 0
    except Exception as exc:
        print("api_account_switch_flow_ok", False)
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