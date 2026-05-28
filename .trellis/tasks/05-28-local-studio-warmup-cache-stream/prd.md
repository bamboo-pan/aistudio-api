# Fix Local Studio Warmup Cache and Streaming Regressions

## Goal

Fix three user-observed Local Studio regressions: Gemini/Google AI Studio warmup does not make the first conversation fast enough, repeated prompts return instantly from an undesired local result cache, and Local Studio stream mode still appears as a one-shot response in the WebUI. The fixes must preserve provider/interface isolation, request-log redaction, Local Studio persistence, and existing base API behavior.

## Requirements

* Remove or disable Local Studio result-reuse caching for chat responses so sending a previously used prompt always makes a fresh upstream request. Do not remove unrelated BotGuard/snapshot caches or provider-native cache mechanisms.
* Update backend and frontend cache settings so Local Studio no longer advertises or sends an always-on result cache. Existing persisted cache files may be ignored; they must not be used for new chat sends.
* Improve Google AI Studio/Gemini warmup so startup warmup prepares the path used by first real Local Studio/base Gemini conversations, not only a shallow browser allocation. Warmup should cover the selected warmup accounts without leaking secrets and should fail softly if upstream/browser warmup is unavailable.
* Make Local Studio stream mode visibly incremental in the browser: backend SSE should emit usable `local_studio.delta` chunks as they arrive, and the UI must render assistant text/thinking during the stream rather than only replacing the conversation after `local_studio.completed`.
* Preserve current error behavior: upstream errors remain controlled SSE/API errors, request logs retain lifecycle phases, and input state recovers after errors.
* Keep OpenAI-compatible and Google provider routing/tool semantics unchanged except where cache removal and streaming display require changes.
* Update tests for cache removal, warmup behavior, and visible/incremental streaming behavior.
* Run complete real system testing in a WSL temp copy per `LOCAL_STUDIO_WEB_REAL_SYSTEM_TEST_PLAN.md`, including API-level and browser UI-level Local Studio verification with request logs enabled.

## Acceptance Criteria

* [x] Repeating the same Local Studio prompt with the same provider/interface/model/options calls upstream again and does not return `cache.hit=true` or cached assistant content.
* [x] Local Studio request payloads from the WebUI no longer include `cache_enabled=true` as a default result-reuse mechanism.
* [x] Existing Local Studio conversations remain readable after cache removal; old assistant cache metadata does not break rendering.
* [x] Startup warmup logs and/or test probes show warmup touches the real browser/account client path needed by first Gemini/Google conversation, and first post-warmup real-system Local Studio Google chat starts streaming within a few seconds when the upstream provider is healthy.
* [x] Stream-on Local Studio API responses include multiple SSE delta events for chunked upstream streams before the final `local_studio.completed` event.
* [x] Stream-on WebUI shows a live assistant placeholder and incremental text/thinking before completion; it does not wait for the final completed conversation to show all output.
* [x] Stream-off mode still returns a single final JSON response and UI behavior remains stable.
* [x] Request logs stay redacted and include client/upstream/client response lifecycle for tested Local Studio cases.
* [x] Unit/static checks pass, including `node --check src/aistudio_api/static/app.js` if the static app is edited.
* [x] WSL real system API and browser UI tests pass or any provider limitation is recorded as a controlled `not_applicable` with evidence; P0 regressions from the system test plan do not recur.

## Verification Results

* Windows full unit suite: `366 passed`; static JS syntax and whitespace checks passed.
* WSL focused warmup/cache/stream/static tests: `94 passed`.
* Expanded WSL real API smoke passed with warmup status `complete` for both real accounts, repeated-prompt upstream groups `2`, OpenAI-compatible stream first delta `5.362s`, browser-backed Gemini first chunk `11.06s`, and Local Studio Google first delta `3.603s`.
* WSL real browser UI smoke passed with repeated prompt fresh-upstream groups `2`; first visible streamed content appeared while busy at `5.808s` and `3.664s`.

## Definition of Done

* Focused unit/static tests are updated for the changed contracts.
* Relevant lint/syntax/test commands pass locally.
* Real API and browser UI system tests run in a WSL temp copy with real credentials and isolated data directories.
* No real tokens, cookies, storage state, generated image payloads, or request-log exports are committed.
* Task files under `.trellis/tasks/05-28-local-studio-warmup-cache-stream/` are committed with the code changes.

## Technical Approach

* Treat the Local Studio request cache as the undesired mechanism: remove chat-route cache lookup/save paths and stop the static UI from forcing `cache_enabled: true` or showing cache as an active run capability.
* Keep `LocalStudioStore` cache helpers only if needed for backward compatibility or existing code references, but do not use them in chat execution.
* Enhance startup/account warmup around `api/app.py` and `AIStudioClient.warmup()` / account pool warmup so it exercises a real low-cost AI Studio route enough to prepare the browser session used by later Gemini conversations.
* Inspect upstream SSE event parsing and frontend `sendLocalStudioStream` rendering. If the backend already emits deltas, ensure the UI updates Alpine state with new message object references so rendering flushes during streaming.
* Add tests that would fail for the current behavior: cache hit avoiding a second upstream call, stream message object mutation not being observable, and warmup not reaching the intended client/account path.

## Decision (ADR-lite)

**Context**: The existing spec documented Local Studio result-reuse cache as intentional, but the user’s real testing shows instant repeated-prompt answers are unacceptable because they make model output untrustworthy.

**Decision**: Remove Local Studio chat result-reuse from the runtime path and UI defaults for this task. Preserve unrelated infrastructure caches and leave old cache files inert.

**Consequences**: Repeated prompts cost real upstream calls again, which is the desired trustworthy behavior. Any future caching must be explicit, provider-native, and visibly labeled so users can distinguish reused content from fresh model output.

## Out of Scope

* Rewriting the whole Local Studio UI.
* Removing BotGuard snapshot cache or browser/session reuse caches needed for authentication/performance.
* Adding a new user-facing cache feature to replace the removed result-reuse cache.
* Changing search/image/reasoning provider semantics except when needed to keep stream rendering and system tests passing.

## Technical Notes

* User-reported issues came from real WebUI testing on 2026-05-28: weak Gemini warmup, instant repeated-prompt results, and ineffective stream mode.
* `src/aistudio_api/api/routes_local_studio.py` currently looks up/saves `store.request_cache_key(...)`, returns cached non-stream results, and has `_stream_cached_local_studio_chat(...)`.
* `src/aistudio_api/static/app.js` currently forces `localStudioCacheEnabled=true`, persists `cacheEnabled:true`, includes `Cache` in pending/run summaries, and sends `cache_enabled:true` from `localStudioOptions()`.
* `tests/unit/test_local_studio.py` currently has tests named `test_chat_route_reuses_local_request_cache` and `test_stream_chat_reuses_local_request_cache`; these need to be inverted or removed according to the new contract.
* `src/aistudio_api/api/app.py` startup warmup currently calls `account_client.warmup()` for selected accounts. Existing tests cover warmup account selection in `tests/unit/test_account_health_and_selection.py`.
* Repo memory notes require `node --check src/aistudio_api/static/app.js` after editing the static Alpine app.
* Real system verification must follow `LOCAL_STUDIO_WEB_REAL_SYSTEM_TEST_PLAN.md` and the workspace `AGENTS.md` WSL temp-copy credential rules.
