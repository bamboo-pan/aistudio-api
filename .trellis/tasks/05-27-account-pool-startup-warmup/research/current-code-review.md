# Current Code Review: Account Pool Startup Warmup

## Cold-start Path

Startup creates the global client and account services in `api/app.py`. The existing `_should_start_background_warmup()` returns true only when browser mode is enabled and `account_count == 0`. When accounts exist, the global warmup is skipped.

Account-backed requests use `_request_account_context()` in `application/api_service.py`. When the rotator and account client pool exist, the selected lease calls `AccountClientPool.get_client(account_id)`. That method creates an account-specific `AIStudioClient`, switches auth, stores it in memory, and returns it. It does not call `warmup()`.

`AIStudioClient.generate_content()` calls `capture_request()` before replay. On a cold account client, capture can launch Camoufox, create a Playwright context with account storage state, navigate to AI Studio, wait for chat runtime readiness, install hooks, capture BotGuard service, capture a model request template, generate a snapshot, and only then replay the user's real body.

## Candidate Selection Review

`AccountRotator.acquire_account()` starts with all available, non-isolated accounts. Default `round_robin` mode delegates to balanced selection, which initially picks the first registry-order account because all stats are equal and `_current_index` starts at zero. `exhaustion` mode prefers the active account when available. Premium/image-preferring models filter to premium accounts when possible.

Warmup should therefore cover:

* active account first in exhaustion mode;
* first non-isolated account for default balanced mode;
* first non-isolated premium account as a bounded extra candidate.

## Chosen Approach

Add small helper functions in `api/app.py` for warmup decisions and candidate selection, then start a background task from lifespan when accounts exist and pure HTTP mode is disabled. The task sequentially calls `AccountClientPool.get_client(account_id)` and `AIStudioClient.warmup()` for bounded candidates.

Sequential warmup avoids launching multiple Camoufox browser processes at the same instant. Failures are logged per account and do not fail startup. The default should be bounded by a new environment setting so users can disable or reduce warmup by setting the limit to zero.

## Rejected for Default Behavior

Default model-template pre-capture is not included in this task. It can reduce first-model latency further, but it requires sending probe prompts through AI Studio and may consume quota or create visible upstream side effects. It should be a separate explicit opt-in feature if needed.