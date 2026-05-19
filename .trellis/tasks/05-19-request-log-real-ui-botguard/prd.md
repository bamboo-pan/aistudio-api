# Fix request log real UI BotGuard smoke

## Goal

Repair the browser-backed request path that currently fails in the built-in WebUI with `Error 500: failed to trigger send while capturing BotGuardService`, and make the request-log feature pass both API-level and frontend UI real-use validation.

## What I Already Know

* The user reproduced the failure from the WebUI Playground: sending `nihao` returns `failed to trigger send while capturing BotGuardService`.
* The request log page remains at `0` records because the failure happens before a replayed outbound request is available to log.
* Existing request-log unit tests use fake replay and streaming sessions, so they do not exercise the real AI Studio page, BotGuard capture, or frontend send flow.
* The user updated `AGENTS.md` to require real testing at both API level and frontend UI actual-use level; this task must follow that bar.

## Requirements

* Fix the real browser-backed chat request path so BotGuard service capture can trigger a send on the current AI Studio UI.
* Preserve existing request replay, streaming, account, and request-log behavior.
* Improve regression coverage so the failure class is covered without requiring live Google access in unit tests.
* Add or document a real WSL validation path that exercises API-level chat and frontend UI actual use, including request-log toggle and saved request inspection.
* Do not count fake-session-only checks as real validation for this task.

## Acceptance Criteria

* [x] Browser-backed WebUI Playground send no longer fails with `failed to trigger send while capturing BotGuardService` in the real WSL environment.
* [x] With request logging enabled from the WebUI, an actual Playground send creates at least one request log entry.
* [x] The WebUI request-log page can refresh, select the saved entry, and display complete details.
* [x] API-level real WSL chat validation passes using the real account credential directory.
* [x] Unit tests cover current and fallback AI Studio send-button detection/triggering.
* [x] Relevant focused unit tests and the full unit suite pass.

## Verification

* Windows focused regression: `C:/Users/bamboo/Desktop/aistudio-api_u1/.venv/Scripts/python.exe -m pytest tests/unit/test_gateway_session_readiness.py tests/unit/test_request_logs.py` - 32 passed.
* Windows full unit suite: `C:/Users/bamboo/Desktop/aistudio-api_u1/.venv/Scripts/python.exe -m pytest tests/unit` - 262 passed.
* Windows compile check: `C:/Users/bamboo/Desktop/aistudio-api_u1/.venv/Scripts/python.exe -m compileall -q src tests` - passed.
* WSL API real smoke in `/home/bamboo/aistudio-api-realtest-botguard` with real credentials at `/home/bamboo/aistudio-api/data/accounts`: request logging enabled, `/v1/chat/completions` for `gemini-3.1-flash-lite` returned `OK`, `/request-logs` total increased to 1, and detail contained raw body plus parsed JSON for `https://alkalimakersuite-pa.clients6.google.com/$rpc/.../GenerateContent`.
* Frontend UI real smoke against `http://127.0.0.1:18092/static/index.html`: opened request records, toggled saving off then on through the UI, sent `frontend ui smoke: reply with OK only` from Playground, received assistant `OK`, opened request records, selected the new `gemma-4-31b-it` entry, and verified `Body JSON`, `Body 原文`, and complete JSON are visible.

## Definition of Done

* The implementation is minimal and consistent with the existing browser session style.
* Task files, tests, and implementation are committed together.
* `git fetch origin` / `origin/master` merge is attempted before final commit; any network blocker is recorded.
* Real WSL validation uses a temporary directory under `/home/bamboo` and the real credentials at `/home/bamboo/aistudio-api/data/accounts`.
* Validation includes both API-level requests and actual frontend UI interaction, not only backend fake clients.

## Technical Approach

Make the AI Studio send trigger more robust at the browser-session boundary. The current code only clicks `button:has-text('Run')`, but the current UI may expose the send action as a different accessible label/icon button or a keyboard-submitted composer. Add a small helper that attempts multiple stable selectors/interaction strategies and reports diagnostics when all fail. Cover this helper with fake-page unit tests. Then run real WSL API and Playwright-driven frontend validation with request logging enabled.

## Decision (ADR-lite)

**Context**: The request-log feature records after replay begins, but the observed failure occurs during BotGuard service capture before replay. Fixing request logging alone would not address the root cause.

**Decision**: Repair the AI Studio composer send trigger in `BrowserSession` and add a real frontend smoke validation for the full user path.

**Consequences**: The browser integration becomes less brittle against AI Studio UI label changes, and future verification must prove both API and WebUI paths instead of relying on fake sessions.

## Out of Scope

* Replacing the browser-backed BotGuard capture architecture.
* Changing request-log storage format or adding deletion/export features.
* Broad frontend redesign unrelated to this failure.

## Research References

* [`research/failure-analysis.md`](research/failure-analysis.md) - failure path and coverage gap analysis.

## Technical Notes

* Primary runtime file: `src/aistudio_api/infrastructure/gateway/session.py`.
* Existing request-log tests: `tests/unit/test_request_logs.py`.
* Existing browser-session tests: `tests/unit/test_gateway_session_readiness.py`.
* Previous request-log task recorded fake-session and WSL smoke success, but the current screenshot proves it did not cover frontend send plus request-log inspection.
* Diagnostic scripts used during this task: `research/inspect_aistudio_dom.py` and `research/probe_aistudio_send.py`.