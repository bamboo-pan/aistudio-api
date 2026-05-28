#!/usr/bin/env python3
"""Real WSL smoke for config UI and account-browser warmup latency.

This script is intentionally task-local. It copies the current checkout to a
fresh WSL run directory, installs it, starts real servers against the real
account directory, and records sanitized timing evidence.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_SOURCE = Path("/mnt/c/Users/bamboo/Desktop/aistudio-api_u1")
DEFAULT_ACCOUNTS_DIR = Path("/home/bamboo/aistudio-api/data/accounts")
TASK_SCRIPT = Path(".trellis/tasks/05-27-visual-configuration-page/system-tests/warmup_real_smoke.py")
TEXT_MODEL = "gemini-3-flash-preview"


class SmokeFailure(RuntimeError):
    pass


def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None, timeout: int | None = None) -> None:
    safe_cmd = " ".join(cmd)
    log(f"run: {safe_cmd}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, timeout=timeout, check=True)


def setup_copy(source: Path, run_root: Path, skip_install: bool) -> Path:
    repo = run_root / "repo"
    repo.parent.mkdir(parents=True, exist_ok=True)
    if repo.exists():
        shutil.rmtree(repo)
    source = source.resolve()
    log(f"copy source: {source} -> {repo}")
    run([
        "rsync",
        "-a",
        "--delete",
        "--exclude", ".git",
        "--exclude", ".venv",
        "--exclude", "venv",
        "--exclude", "__pycache__",
        f"{source}/",
        f"{repo}/",
    ])
    venv = repo / "venv"
    if not skip_install:
        run([sys.executable, "-m", "venv", str(venv)], cwd=repo, timeout=120)
        python = venv / "bin" / "python"
        run([str(python), "-m", "pip", "install", "--upgrade", "pip"], cwd=repo, timeout=300)
        run([str(python), "-m", "pip", "install", "-e", "."], cwd=repo, timeout=600)
        try:
            run([str(python), "-m", "playwright", "install", "firefox"], cwd=repo, timeout=600)
        except subprocess.CalledProcessError as exc:
            raise SmokeFailure("playwright firefox install failed") from exc
    return repo


@dataclass
class Server:
    repo: Path
    run_root: Path
    label: str
    port: int
    camoufox_port: int
    warmup_limit: int
    accounts_dir: Path
    process: subprocess.Popen[str] | None = None
    lines: list[str] = field(default_factory=list)
    _condition: threading.Condition = field(default_factory=threading.Condition)
    _reader: threading.Thread | None = None

    def env(self) -> dict[str, str]:
        data_root = self.run_root / "data" / self.label
        env = os.environ.copy()
        proxy_server = env.get("AISTUDIO_PROXY_SERVER") or env.get("https_proxy") or env.get("HTTPS_PROXY") or env.get("http_proxy") or env.get("HTTP_PROXY")
        env.update({
            "PYTHONUNBUFFERED": "1",
            "AISTUDIO_PORT": str(self.port),
            "AISTUDIO_CAMOUFOX_PORT": str(self.camoufox_port),
            "AISTUDIO_LOGIN_CAMOUFOX_PORT": str(self.camoufox_port + 100),
            "AISTUDIO_ACCOUNT_WARMUP_LIMIT": str(self.warmup_limit),
            "AISTUDIO_ACCOUNTS_DIR": str(self.accounts_dir),
            "AISTUDIO_REQUEST_LOGS_DIR": str(data_root / "request-logs"),
            "AISTUDIO_LOCAL_STUDIO_DIR": str(data_root / "local-studio"),
            "AISTUDIO_GENERATED_IMAGES_DIR": str(data_root / "generated-images"),
            "AISTUDIO_IMAGE_SESSIONS_DIR": str(data_root / "image-sessions"),
            "AISTUDIO_CONFIG_ENV_FILE": str(data_root / "config.env"),
            "AISTUDIO_CAMOUFOX_HEADLESS": os.environ.get("AISTUDIO_CAMOUFOX_HEADLESS", "1"),
        })
        if proxy_server:
            env["AISTUDIO_PROXY_SERVER"] = proxy_server
        return env

    def start(self) -> None:
        python = self.repo / "venv" / "bin" / "python"
        if not python.exists():
            python = Path(sys.executable)
        log_file = self.run_root / f"server-{self.label}.log"
        log(f"starting server {self.label}: port={self.port} warmup_limit={self.warmup_limit}")
        self.process = subprocess.Popen(
            [str(python), "main.py", "server", "--port", str(self.port), "--camoufox-port", str(self.camoufox_port)],
            cwd=str(self.repo),
            env=self.env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        def reader() -> None:
            assert self.process is not None and self.process.stdout is not None
            with log_file.open("w", encoding="utf-8") as handle:
                for line in self.process.stdout:
                    sanitized = line.rstrip("\n")
                    handle.write(sanitized + "\n")
                    handle.flush()
                    if any(marker in sanitized for marker in (
                        "Starting account browser warmup",
                        "Account browser warmup completed",
                        "Account browser warmup failed",
                        "Client initialized",
                        "Application startup complete",
                    )):
                        log(f"{self.label}: {sanitized}")
                    with self._condition:
                        self.lines.append(sanitized)
                        self._condition.notify_all()

        self._reader = threading.Thread(target=reader, daemon=True)
        self._reader.start()
        self.wait_http("/health", timeout=45)

    def wait_http(self, path: str, timeout: float) -> dict[str, Any]:
        import httpx

        deadline = time.monotonic() + timeout
        url = f"http://127.0.0.1:{self.port}{path}"
        last_error = ""
        while time.monotonic() < deadline:
            if self.process is not None and self.process.poll() is not None:
                raise SmokeFailure(f"server {self.label} exited early with {self.process.returncode}")
            try:
                response = httpx.get(url, timeout=2)
                if response.status_code == 200:
                    return response.json()
                last_error = f"HTTP {response.status_code}: {response.text[:160]}"
            except Exception as exc:  # noqa: BLE001 - diagnostic for smoke harness
                last_error = str(exc)
            time.sleep(0.5)
        raise SmokeFailure(f"server {self.label} did not become ready at {path}: {last_error}")

    def wait_log(self, pattern: str, timeout: float) -> str:
        regex = re.compile(pattern)
        deadline = time.monotonic() + timeout
        with self._condition:
            while True:
                for line in self.lines:
                    if regex.search(line):
                        return line
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    tail = "\n".join(self.lines[-20:])
                    raise SmokeFailure(f"timed out waiting for log {pattern!r} in {self.label}; tail:\n{tail}")
                self._condition.wait(timeout=min(1.0, remaining))

    def wait_log_count(self, pattern: str, count: int, timeout: float) -> list[str]:
        regex = re.compile(pattern)
        deadline = time.monotonic() + timeout
        with self._condition:
            while True:
                matches = [line for line in self.lines if regex.search(line)]
                if len(matches) >= count:
                    return matches[:count]
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    tail = "\n".join(self.lines[-20:])
                    raise SmokeFailure(f"timed out waiting for {count} log matches {pattern!r} in {self.label}; tail:\n{tail}")
                self._condition.wait(timeout=min(1.0, remaining))

    def stop(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            log(f"stopping server {self.label}")
            self.process.terminate()
            try:
                self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        if self._reader is not None:
            self._reader.join(timeout=5)


def account_count(accounts_dir: Path) -> int:
    registry = accounts_dir / "registry.json"
    if not registry.exists():
        raise SmokeFailure(f"account registry not found: {registry}")
    data = json.loads(registry.read_text(encoding="utf-8"))
    accounts = data.get("accounts") or {}
    if not accounts:
        raise SmokeFailure("real account registry is empty")
    return len(accounts)


def parse_warmup_candidate_count(line: str) -> int:
    match = re.search(r"accounts=\[(.*?)\]", line)
    if not match:
        return 1
    content = match.group(1).strip()
    if not content:
        return 0
    return len([part for part in content.split(",") if part.strip()])


def redact_account_ids(text: str) -> str:
    return re.sub(r"acc_[A-Za-z0-9_.-]+", "acc_<redacted>", text)


def measure_stream_chat(server: Server, label: str, *, timeout_seconds: float, allow_timeout: bool = False) -> dict[str, Any]:
    import httpx

    payload = {
        "model": TEXT_MODEL,
        "messages": [{"role": "user", "content": f"Reply exactly OK. real warmup smoke {label} {uuid.uuid4().hex}"}],
        "stream": True,
        "stream_options": {"include_usage": True},
        "thinking": "off",
    }
    url = f"http://127.0.0.1:{server.port}/v1/chat/completions"
    first_event_ms: float | None = None
    text_parts: list[str] = []
    error_text = ""
    start = time.monotonic()
    log(f"measuring first streamed chat: {label}")
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout_seconds, connect=30.0)) as client:
            with client.stream("POST", url, json=payload) as response:
                status = response.status_code
                if status != 200:
                    body = response.read().decode("utf-8", errors="replace")
                    raise SmokeFailure(f"{label} chat returned HTTP {status}: {body[:500]}")
                for line in response.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if not data:
                        continue
                    if data == "[DONE]":
                        break
                    if first_event_ms is None:
                        first_event_ms = (time.monotonic() - start) * 1000
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if event.get("error"):
                        error_text = json.dumps(event.get("error"), ensure_ascii=False)
                    for choice in event.get("choices") or []:
                        delta = choice.get("delta") or {}
                        if isinstance(delta.get("content"), str):
                            text_parts.append(delta["content"])
    except httpx.ReadTimeout:
        total_ms = (time.monotonic() - start) * 1000
        if not allow_timeout:
            raise SmokeFailure(f"{label} chat timed out after {round(total_ms, 1)} ms")
        result = {
            "label": label,
            "status": "timeout",
            "timed_out": True,
            "timeout_seconds": timeout_seconds,
            "first_event_ms": round(total_ms, 1),
            "total_ms": round(total_ms, 1),
            "assistant_text_preview": "",
        }
        log(f"{label}: timed out before first SSE event after {result['total_ms']} ms")
        return result
    total_ms = (time.monotonic() - start) * 1000
    text = "".join(text_parts).strip()
    if error_text:
        raise SmokeFailure(f"{label} chat SSE error: {error_text[:500]}")
    if first_event_ms is None:
        raise SmokeFailure(f"{label} chat produced no SSE data events")
    if not text:
        raise SmokeFailure(f"{label} chat produced no assistant text")
    result = {
        "label": label,
        "status": 200,
        "timed_out": False,
        "first_event_ms": round(first_event_ms, 1),
        "total_ms": round(total_ms, 1),
        "assistant_text_preview": text[:80],
    }
    log(f"{label}: first_event_ms={result['first_event_ms']} total_ms={result['total_ms']} text={text[:40]!r}")
    return result


def get_config_item(port: int, key: str) -> dict[str, Any]:
    import httpx

    response = httpx.get(f"http://127.0.0.1:{port}/config", timeout=10)
    response.raise_for_status()
    for item in response.json().get("data") or []:
        if item.get("key") == key:
            return item
    raise SmokeFailure(f"config key missing: {key}")


def run_api_config_smoke(server: Server) -> dict[str, Any]:
    import httpx

    log("running config API smoke")
    response = httpx.get(f"http://127.0.0.1:{server.port}/config", timeout=10)
    response.raise_for_status()
    body = response.json()
    keys = {item.get("key") for item in body.get("data") or []}
    required = {"AISTUDIO_USE_PURE_HTTP", "AISTUDIO_ACCOUNT_WARMUP_LIMIT"}
    missing = required - keys
    if missing:
        raise SmokeFailure(f"config API missing keys: {sorted(missing)}")
    pure = get_config_item(server.port, "AISTUDIO_USE_PURE_HTTP")
    warmup = get_config_item(server.port, "AISTUDIO_ACCOUNT_WARMUP_LIMIT")
    if "skip" not in str(pure.get("description", "")).lower() and "跳过" not in str(pure.get("description", "")):
        raise SmokeFailure("Pure HTTP description does not explain skipped warmup")
    if "Pure HTTP" not in str(warmup.get("description", "")) and "Pure" not in str(warmup.get("description", "")):
        raise SmokeFailure("warmup limit description does not mention Pure HTTP boundary")

    put = httpx.put(
        f"http://127.0.0.1:{server.port}/config/AISTUDIO_ACCOUNT_WARMUP_LIMIT",
        json={"value": 3},
        timeout=10,
    )
    put.raise_for_status()
    saved = put.json()
    if saved.get("configured_value") != 3 or not saved.get("is_overridden"):
        raise SmokeFailure(f"config API save did not persist override: {saved}")
    delete = httpx.delete(f"http://127.0.0.1:{server.port}/config/AISTUDIO_ACCOUNT_WARMUP_LIMIT", timeout=10)
    delete.raise_for_status()
    reset = delete.json()
    if reset.get("is_overridden"):
        raise SmokeFailure(f"config API reset left override active: {reset}")
    return {
        "env_file": body.get("env_file"),
        "item_count": len(body.get("data") or []),
        "required_keys_present": sorted(required),
        "save_reset_key": "AISTUDIO_ACCOUNT_WARMUP_LIMIT",
    }


async def run_ui_config_smoke_async(server: Server) -> dict[str, Any]:
    from playwright.async_api import async_playwright
    import httpx

    log("running config browser UI smoke")
    console_errors: list[str] = []
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1366, "height": 900})
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        await page.goto(f"http://127.0.0.1:{server.port}/static/index.html#config", wait_until="networkidle", timeout=60_000)
        await page.wait_for_selector(".config-row code", timeout=30_000)
        codes = await page.locator(".config-row code").all_inner_texts()
        for key in ("AISTUDIO_USE_PURE_HTTP", "AISTUDIO_ACCOUNT_WARMUP_LIMIT"):
            if key not in codes:
                raise SmokeFailure(f"config UI missing key: {key}")
        warmup_row = page.locator(".config-row").filter(has_text="AISTUDIO_ACCOUNT_WARMUP_LIMIT").first
        await warmup_row.locator("input.config-input").fill("4")
        await warmup_row.get_by_role("button", name=re.compile("保存")).click()

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            item = get_config_item(server.port, "AISTUDIO_ACCOUNT_WARMUP_LIMIT")
            if item.get("configured_value") == 4 and item.get("is_overridden"):
                break
            await page.wait_for_timeout(250)
        else:
            raise SmokeFailure("config UI save did not update API state")

        await warmup_row.get_by_role("button", name="重置").click()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            item = get_config_item(server.port, "AISTUDIO_ACCOUNT_WARMUP_LIMIT")
            if not item.get("is_overridden"):
                break
            await page.wait_for_timeout(250)
        else:
            raise SmokeFailure("config UI reset did not clear API state")

        screenshot = server.run_root / "config-ui-smoke.png"
        await page.screenshot(path=str(screenshot), full_page=False)
        await browser.close()

    unexpected_console_errors = [
        text for text in console_errors
        if "Failed to load resource" not in text and "404" not in text
    ]
    if unexpected_console_errors:
        raise SmokeFailure("unexpected browser console errors: " + " | ".join(unexpected_console_errors[:3]))
    # Confirm service still healthy after browser save/reset.
    with httpx.Client(timeout=10) as client:
        health = client.get(f"http://127.0.0.1:{server.port}/health")
        health.raise_for_status()
    return {
        "route": "#config",
        "keys_visible": ["AISTUDIO_USE_PURE_HTTP", "AISTUDIO_ACCOUNT_WARMUP_LIMIT"],
        "save_reset_key": "AISTUDIO_ACCOUNT_WARMUP_LIMIT",
        "screenshot": str(screenshot),
        "ignored_console_404_count": len(console_errors) - len(unexpected_console_errors),
    }


def run_ui_config_smoke(server: Server) -> dict[str, Any]:
    return asyncio.run(run_ui_config_smoke_async(server))


def run_in_repo(args: argparse.Namespace) -> dict[str, Any]:
    accounts_dir = Path(args.accounts_dir)
    if not accounts_dir.is_dir():
        raise SmokeFailure(f"accounts directory not found: {accounts_dir}")
    accounts = account_count(accounts_dir)
    log(f"real account registry loaded: count={accounts}")

    run_root = Path(args.run_root).resolve()
    repo = Path.cwd().resolve()
    results: dict[str, Any] = {
        "run_root": str(run_root),
        "repo": str(repo),
        "accounts_count": accounts,
        "model": TEXT_MODEL,
    }

    cold = Server(repo, run_root, "warmup_off", args.port_base, args.camoufox_port_base, 0, accounts_dir)
    warm = Server(repo, run_root, "warmup_on", args.port_base + 1, args.camoufox_port_base + 10, args.warmup_on_limit, accounts_dir)
    try:
        cold.start()
        results["warmup_off"] = measure_stream_chat(
            cold,
            "warmup_off_first_chat",
            timeout_seconds=args.chat_timeout,
            allow_timeout=True,
        )
    finally:
        cold.stop()

    try:
        warm.start()
        started = time.monotonic()
        warmup_start_log = warm.wait_log(r"Starting account browser warmup", timeout=10)
        expected_warmups = max(1, parse_warmup_candidate_count(warmup_start_log))
        results["warmup_on_start_log"] = warmup_start_log
        warmup_logs = warm.wait_log_count(r"Account browser warmup completed", expected_warmups, timeout=args.warmup_timeout)
        warmup_ready_ms = (time.monotonic() - started) * 1000
        results["warmup_on_logs"] = warmup_logs
        results["warmup_on_ready_ms"] = round(warmup_ready_ms, 1)
        results["warmup_on"] = measure_stream_chat(
            warm,
            "warmup_on_first_chat",
            timeout_seconds=args.chat_timeout,
        )
        results["config_api"] = run_api_config_smoke(warm)
        results["config_ui"] = run_ui_config_smoke(warm)
        results["post_smoke_health"] = warm.wait_http("/health", timeout=10)
    finally:
        warm.stop()

    off_ms = results["warmup_off"]["first_event_ms"]
    on_ms = results["warmup_on"]["first_event_ms"]
    total_off = results["warmup_off"]["total_ms"]
    total_on = results["warmup_on"]["total_ms"]
    results["comparison"] = {
        "first_event_delta_ms": round(off_ms - on_ms, 1),
        "first_event_speedup_ratio": round(off_ms / on_ms, 2) if on_ms else None,
        "total_delta_ms": round(total_off - total_on, 1),
        "total_speedup_ratio": round(total_off / total_on, 2) if total_on else None,
        "prewarmed_first_event_faster": on_ms < off_ms,
        "prewarmed_total_faster": total_on < total_off,
    }
    if not results["comparison"]["prewarmed_first_event_faster"]:
        raise SmokeFailure(f"prewarmed first SSE event was not faster: {results['comparison']}")

    result_path = run_root / "warmup-real-smoke-results.json"
    result_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"results: {result_path}")
    return results


def write_report(results: dict[str, Any], report_out: Path) -> None:
    comparison = results["comparison"]
    lines = [
        "# Real WSL Warmup and Config Smoke Result",
        "",
        f"Run root: `{results['run_root']}`",
        f"Model: `{results['model']}`",
        f"Real account count: {results['accounts_count']}",
        "",
        "## Warmup Timing",
        "",
        "| Scenario | First SSE event | Total stream |",
        "| --- | ---: | ---: |",
        f"| warmup off | {results['warmup_off']['first_event_ms']} ms | {results['warmup_off']['total_ms']} ms |",
        f"| warmup on | {results['warmup_on']['first_event_ms']} ms | {results['warmup_on']['total_ms']} ms |",
        "",
        f"First-event speedup: {comparison['first_event_delta_ms']} ms ({comparison['first_event_speedup_ratio']}x).",
        f"Total stream delta: {comparison['total_delta_ms']} ms ({comparison['total_speedup_ratio']}x).",
        "Warmup completions before request:",
        *[f"- `{redact_account_ids(line)}`" for line in results["warmup_on_logs"]],
        "",
        "## Config API/UI Smoke",
        "",
        f"Config API item count: {results['config_api']['item_count']}",
        f"Config API save/reset key: `{results['config_api']['save_reset_key']}`",
        f"Config UI route: `{results['config_ui']['route']}`",
        f"Config UI save/reset key: `{results['config_ui']['save_reset_key']}`",
        f"Screenshot artifact: `{results['config_ui']['screenshot']}`",
        "",
        "Secrets: raw account cookies, storage state, API tokens, request logs, and screenshots are not committed.",
        "",
    ]
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text("\n".join(lines), encoding="utf-8")
    log(f"wrote report: {report_out}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="Source checkout to copy when not running in the temp repo")
    parser.add_argument("--run-root", default="", help="WSL run root; defaults to /home/bamboo/aistudio-api-warmup-<timestamp>")
    parser.add_argument("--accounts-dir", default=str(DEFAULT_ACCOUNTS_DIR))
    parser.add_argument("--report-out", default="")
    parser.add_argument("--port-base", type=int, default=18080)
    parser.add_argument("--camoufox-port-base", type=int, default=19220)
    parser.add_argument("--warmup-timeout", type=int, default=180)
    parser.add_argument("--chat-timeout", type=int, default=180)
    parser.add_argument("--warmup-on-limit", type=int, default=2)
    parser.add_argument("--in-repo", action="store_true")
    parser.add_argument("--skip-install", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if not args.run_root:
            args.run_root = f"/home/bamboo/aistudio-api-warmup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        run_root = Path(args.run_root).resolve()
        if not args.in_repo:
            repo = setup_copy(Path(args.source), run_root, args.skip_install)
            python = repo / "venv" / "bin" / "python"
            if args.skip_install:
                python = Path(sys.executable)
            cmd = [
                str(python),
                str(repo / TASK_SCRIPT),
                "--in-repo",
                "--run-root", str(run_root),
                "--accounts-dir", args.accounts_dir,
                "--port-base", str(args.port_base),
                "--camoufox-port-base", str(args.camoufox_port_base),
                "--warmup-timeout", str(args.warmup_timeout),
                "--chat-timeout", str(args.chat_timeout),
                "--warmup-on-limit", str(args.warmup_on_limit),
            ]
            if args.report_out:
                cmd.extend(["--report-out", args.report_out])
            run(cmd, cwd=repo, timeout=1800)
            return 0

        results = run_in_repo(args)
        print("RESULT_JSON=" + json.dumps(results, ensure_ascii=False, sort_keys=True), flush=True)
        if args.report_out:
            write_report(results, Path(args.report_out))
        return 0
    except SmokeFailure as exc:
        log(f"SMOKE FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
