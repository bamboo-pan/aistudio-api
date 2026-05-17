# fix web auth retry

## Goal

Fix the browser-backed web/API path where `/v1/chat/completions` streaming still fails with AI Studio authentication or permission errors after snapshot cache invalidation and manual account activation.

## What I already know

* The reported failure happens after a successful hook capture for `models/gemini-3.1-flash-lite` and then upstream returns `[7,"The caller does not have permission"]` or `[16,"Request had invalid authentication credentials"]`.
* The first stream retry currently clears only the snapshot cache and forces a new snapshot capture.
* Account activation clears `BrowserSession` state and the global snapshot cache.
* `RequestCaptureService` also has its own per-model template cache, and the reported post-activation log lacks a fresh `Hook 模板已就绪`, which indicates the old service-level template can be reused after switching accounts.
* Reusing an old captured template can carry stale request headers/body context across browser auth changes even when the snapshot itself is regenerated.

## Assumptions

* The root bug is stale capture template reuse across account auth changes and auth-error retries, not a general model capability issue.
* Existing account rotation and manual activation semantics should remain unchanged except for invalidating browser capture state more completely.

## Requirements

* Switching accounts through the web UI, completed login activation, or automatic rotator must clear capture templates in addition to browser session templates and snapshot cache.
* Streaming auth-error retry must force a fresh capture path that cannot reuse stale templates from the previous auth context.
* Non-streaming replay behavior must keep using the captured request contract: captured URL and sanitized headers are passed into browser replay.
* Tests must cover template invalidation after account switching and preserve the captured request replay contract.

## Acceptance Criteria

* [x] After activating another account, the next capture for an already-used model re-captures its template before replaying.
* [x] OpenAI-compatible streaming auth retry clears all browser-backed capture state needed for a fresh replay attempt.
* [x] Gemini streaming path has the same retry behavior.
* [x] Existing unit tests pass, with focused tests for capture template reset and account activation wiring.
* [x] Real WSL environment test runs for a browser-backed chat request because this touches API/account/browser/gateway behavior.

## Definition of Done

* Focused unit tests added or updated.
* Relevant backend tests pass locally.
* Real WSL browser-backed test is executed with actual account credentials.
* Task files are committed with the code changes.

## Out of Scope

* Changing model selection policy or premium/non-premium account routing.
* Reworking BotGuard snapshot generation.
* Adding new frontend controls.

## Technical Notes

* Relevant spec: `.trellis/spec/backend/quality-guidelines.md`, especially the captured request replay contract.
* Likely code paths: `AIStudioClient`, `RequestCaptureService`, `AccountService.activate_account`, account routes, `_try_switch_account`, and streaming response builders.
