# Balanced Account Pool for Concurrent Requests

## Goal

Replace the current `round_robin` behavior with a balanced account-pool mode that can distribute concurrent and multi-user traffic across available accounts without globally switching browser auth for every request. The goal is to reduce supplier-side detection/rate-limit pressure from overusing one account while keeping end-user requests and conversations continuous.

## What I already know

- The current UI exposes `exhaustion` and `round_robin`, but normal request paths only call account selection when the active account is missing, isolated, unsuitable for premium/image models, or after a 429 retry.
- The current runtime has one global `AIStudioClient`, one global browser session/auth state, and one global active account.
- Switching accounts through `AccountService.activate_account()` calls `client.switch_auth()` and clears capture/snapshot state. This is unsafe for concurrent in-flight requests if used as the balancing mechanism.
- Users want an account pool for multiple users, more accounts over time, and overall balanced usage. They do not want a single user's every request to jump accounts if avoidable.
- User-visible chat continuity must not break because the backend selected a different account.

## Requirements

- Rework `round_robin` into a balanced account mode for normal request handling.
- Balanced mode must distribute total traffic across available healthy accounts instead of keeping all normal traffic on the currently active account.
- A request must be bound to the account selected for that request, including success/error/rate-limit accounting.
- Backend account selection must be invisible to API callers and the Web UI.
- Concurrent requests must not share mutable global auth/capture state in a way that lets one request's account switch affect another request.
- The system should prefer keeping a stable account for a logical user/session when possible, so one user's consecutive requests do not change account every turn solely due to balancing.
- Premium-preferred models must still use healthy Pro/Ultra accounts when available.
- 429/rate-limit handling must cool down the account that actually handled the failed request and retry on another eligible account.
- Existing exhaustion mode should keep its existing current-account-until-unavailable behavior.
- Existing manual account activation and force-next APIs should remain usable.

## Acceptance Criteria

- [ ] In balanced mode, two or more concurrent normal text requests with two eligible accounts can be assigned to different accounts.
- [ ] Success, rate-limit, and error stats are recorded against the bound account, not whichever account is active at record time.
- [ ] A request using one account does not call global `activate_account()` to switch auth before sending the upstream request.
- [ ] Existing premium/image routing still switches away from a free account when a Pro/Ultra account is available.
- [ ] Exhaustion mode continues to keep the current active account until it becomes unavailable.
- [ ] Unit tests cover balanced request distribution, request-bound accounting, retry after 429, and stable user/session affinity.
- [ ] Relevant test suite passes.
- [ ] Per project instructions, WSL real-environment smoke testing is run because this changes API/account/gateway behavior.

## Out of Scope

- Full distributed/multi-process scheduling across multiple server instances.
- Persistent user-to-account affinity stored in a database.
- A separate browser process per account beyond what the local `AIStudioClient`/`BrowserSession` abstraction already creates.
- Changing public API request/response schemas for callers.

## Technical Notes

- Main files inspected: `src/aistudio_api/application/account_rotator.py`, `src/aistudio_api/application/api_service.py`, `src/aistudio_api/application/account_service.py`, `src/aistudio_api/infrastructure/gateway/client.py`, `src/aistudio_api/api/state.py`, `src/aistudio_api/api/app.py`.
- `AIStudioClient` owns a `BrowserSession`, capture service, replay service, and streaming gateway. This makes a per-account client pool feasible.
- Current `BrowserSession` has a single-thread executor and mutable auth/templates, so per-account isolation should happen at the client/session level, not by rapidly switching one shared session.
- Research artifact: `.trellis/tasks/05-17-balanced-account-pool/research/current-account-routing.md`.

## Verification

- `python -m pytest tests/unit/test_account_health_and_selection.py -q` -> 23 passed.
- `python -m pytest tests/unit/test_openai_compatibility.py tests/unit/test_gemini_native_routes.py tests/unit/test_streaming_stability.py tests/unit/test_gateway_session_readiness.py tests/unit/test_image_generation_service.py -q` -> 86 passed.
- `python -m pytest tests/unit -q` -> 236 passed.
- WSL real smoke in `/home/bamboo/aistudio-api-realtest-balanced` with real credentials at `/home/bamboo/aistudio-api/data/accounts`: two OpenAI-compatible chat requests using different `user` affinity keys both returned `OK`, and `/rotation` showed the two real accounts each recorded `requests=1`, `success=1`, `in_flight=0`.
