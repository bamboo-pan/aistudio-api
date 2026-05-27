# Warm account pool on startup

## Goal

Reduce the slow first user request after service startup when stored Google accounts are configured. The service should warm the browser-backed account client pool in the background so the first real request is less likely to pay the full Camoufox launch, AI Studio navigation, and chat runtime readiness cost.

## What I Already Know

* Startup currently creates a global `AIStudioClient` and an `AccountClientPool`.
* Existing background browser warmup only runs when there are zero stored accounts and pure HTTP mode is disabled.
* Real account-backed requests use `AccountClientPool.get_client(account_id)` lazily through request-scoped account selection.
* `AccountClientPool.get_client()` creates an account-specific `AIStudioClient` and switches auth, but it does not warm that client's browser context.
* First browser-backed generation still needs request template capture and BotGuard snapshot generation before replay.

## Assumptions

* The target improvement is startup-adjacent cold browser/context latency, not model generation latency.
* Startup must remain responsive; account warmup should run in a background task and tolerate failures.
* Default behavior should not proactively capture model templates because that triggers AI Studio sends and may consume quota or create upstream side effects.
* Warming a bounded set of likely first-use accounts is safer than warming every account by default.

## Requirements

* Add background warmup for account-specific clients when stored accounts exist and browser mode is enabled.
* Skip account-pool warmup in pure HTTP mode.
* Do not block FastAPI startup on account-pool warmup.
* Warm likely first-use account candidates:
  * active account first for exhaustion mode when available;
  * registry-order first healthy account for balanced/default mode;
  * first healthy premium account as an additional candidate when within the configured limit.
* Keep warmup bounded and configurable so users can reduce or disable startup resource usage.
* Log per-account warmup success/failure without failing startup.
* Preserve existing zero-account global warmup behavior.

## Acceptance Criteria

* [x] With zero accounts and browser mode, existing global background warmup still starts.
* [x] With one or more accounts and browser mode, account-pool background warmup starts for bounded candidates.
* [x] With pure HTTP mode, no browser warmup starts.
* [x] Candidate selection covers balanced/default, exhaustion, isolated-account, and premium-account cases.
* [x] Unit tests cover warmup decision and candidate selection behavior.
* [x] Real WSL API smoke confirms a browser-backed request succeeds after startup with real credentials.
* [x] Real frontend UI smoke confirms Local Studio/Playground can send after startup with real credentials.

## Verification

* `C:/Users/bamboo/Desktop/aistudio-api_u1/.venv/Scripts/python.exe -m pytest tests/unit/test_account_health_and_selection.py -q` -- 30 passed.
* `C:/Users/bamboo/Desktop/aistudio-api_u1/.venv/Scripts/python.exe -m pytest tests/unit -q` -- 357 passed.
* WSL real smoke: `bash .trellis/tasks/05-27-account-pool-startup-warmup/verification/run_wsl_warmup_smoke.sh` copied the current workspace to `/home/bamboo/aistudio-api-warmup-smoke-20260527-203224`, used real credentials at `/home/bamboo/aistudio-api/data/accounts`, and did not print credential contents.
* WSL smoke result: account browser warmup started and completed, no warmup failure log was present, `/v1/chat/completions` returned HTTP 200 with `pong`, and frontend Local Studio loaded models and sent a message returning `OK.`.
* WSL smoke artifacts: `/home/bamboo/aistudio-api-warmup-smoke-20260527-203224/artifacts/summary.md` and `/home/bamboo/aistudio-api-warmup-smoke-20260527-203224/artifacts/results.json`.

## Definition of Done

* Tests added or updated for warmup helper behavior.
* Relevant unit tests pass locally.
* Real WSL API and frontend UI smoke tests pass because this touches account/browser/gateway startup behavior.
* Task files, code changes, and verification notes are committed on the feature branch.

## Out of Scope

* Default model-template pre-capture.
* Changing BotGuard snapshot generation semantics.
* Reworking account rotation strategy.
* Persisting BotGuard snapshots across service restarts.

## Technical Notes

* Startup warmup decision lives in `src/aistudio_api/api/app.py`.
* Request-scoped account client creation lives in `src/aistudio_api/application/account_client_pool.py`.
* Browser context warmup is `AIStudioClient.warmup()` -> `BrowserSession.ensure_context()`.
* Account selection starts in `src/aistudio_api/application/api_service.py` and delegates to `AccountRotator.acquire_account()`.
* Detailed code-path review is in `research/current-code-review.md`.