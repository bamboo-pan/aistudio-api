# Fix replay captured URL failure

## Goal

Restore browser-backed AI Studio replay after successful hook capture so `/v1/chat/completions` no longer returns `502 Bad Gateway` with `no captured URL available for replay`.

## What I Already Know

* The runtime logs show template capture and snapshot generation succeeding before replay fails.
* The failing error is raised by `BrowserSession._get_captured_info()` when the session-level template cache has no URL.
* The browser capture path currently keeps template state in both `RequestCaptureService` and `BrowserSession`.
* Account switching clears `BrowserSession` templates but does not clear `RequestCaptureService` templates, so capture can return a cached template while replay cannot find session template URL/header state.

## Requirements

* Non-streaming browser replay must use the URL and headers from the `CapturedRequest` returned by capture.
* Streaming browser replay must follow the same captured request source so it does not depend on hidden session template state.
* Reusing a cached capture template after account switching must not produce `no captured URL available for replay`.
* Keep pure HTTP replay behavior unchanged.

## Acceptance Criteria

* [x] Unit tests cover browser replay using a `CapturedRequest` even when session templates are empty.
* [x] Unit tests cover streaming replay using the `CapturedRequest` URL and headers.
* [x] Existing gateway/session tests still pass.
* [x] WSL real environment test passes for a text chat request using real credentials.

## Out of Scope

* Reworking account rotation policy.
* Changing snapshot generation logic.
* Changing pure HTTP mode capability limits.

## Technical Notes

* Primary code path: capture service -> replay service -> browser session XHR replay.
* Suspected root fix: pass captured URL/headers into browser replay methods instead of asking `BrowserSession` to rediscover them from its internal template cache.

## Verification

* Windows unit suite: `206 passed`.
* WSL targeted gateway tests: `13 passed`.
* WSL real server test with copied real credentials: `gemini-3-flash-preview` returned `200 OK` for first request and cached repeat request.
* WSL account-switch check: `gemini-3.1-flash-lite` no longer failed with local `no captured URL available for replay`; it reached upstream and returned account/model permission `401`.