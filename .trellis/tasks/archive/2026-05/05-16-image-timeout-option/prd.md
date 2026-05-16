# Add Image Generation Timeout Option

## Goal

Let users configure image generation timeout from the API request and WebUI instead of requiring an environment variable change. The existing default remains `AISTUDIO_TIMEOUT_REPLAY=120` seconds when no request override is provided.

## Requirements

* Add an optional request-level `timeout` field to `/v1/images/generations`.
* Validate `timeout` as a positive integer number of seconds and reject invalid values before upstream calls.
* Forward an explicit image timeout to the replay boundary only when supplied; otherwise keep the current `settings.timeout_replay` / `AISTUDIO_TIMEOUT_REPLAY` default path.
* Add a WebUI image generation timeout control with a clear default behavior: blank means server default.
* Include timeout in retry/session request state so repeat generation uses the same chosen timeout.
* Update Chinese and English README docs to mention the request/UI override.

## Acceptance Criteria

* [x] `ImageRequest(timeout=241)` forwards `timeout=241` to `AIStudioClient.generate_image()`.
* [x] Omitting `timeout` still forwards no per-call timeout and therefore uses `settings.timeout_replay`.
* [x] Invalid timeout values are rejected as `400 invalid_request_error` without calling the client.
* [x] The static image UI exposes a timeout control and sends `timeout` only when the user sets a positive value.
* [x] README and README_EN document that env config remains the default and UI/API timeout can override per request.

## Definition of Done

* Unit/static regression tests updated and passing.
* Relevant backend specs checked before implementation and verification.
* Real WSL credential test run for image/API behavior because this changes image generation request plumbing.
* Task files committed with the implementation.

## Technical Approach

Use a conservative request-level override. Extend `ImageRequest` with `timeout: Optional[int] = None`, validate it in image request validation, pass it through `handle_image_generation()` and `AIStudioClient.generate_image()`, then into `RequestReplayService.replay()`. The replay service already falls back to `settings.timeout_replay` when `timeout is None`, preserving the default environment-variable behavior.

On the WebUI image page, add a compact numeric seconds input in the existing image parameter grid. Store the value in Alpine state as `imageTimeout`; blank or invalid values omit the field, while positive integers are serialized as `timeout`.

## Decision (ADR-lite)

**Context**: Users need a simpler way to increase image generation timeout than setting environment variables, especially for occasional large image requests.

**Decision**: Add a per-request timeout override to the image generation API and expose it in the image generation WebUI.

**Consequences**: Existing deployments keep the same default timeout. API clients and UI users can opt into longer waits per request without changing process configuration. This does not add a global mutable runtime settings endpoint.

## Out of Scope

* A global runtime settings page for all environment variables.
* Timeout controls for chat completions, streaming, request capture, or prompt optimization.
* Persisting a global default timeout across browsers/users.

## Technical Notes

* `settings.timeout_replay` in `src/aistudio_api/config.py` is already backed by `AISTUDIO_TIMEOUT_REPLAY` with default `120`.
* `RequestReplayService.replay(..., timeout=None)` already falls back to `settings.timeout_replay`.
* Current image request schema forbids extra fields, so `timeout` must be explicit in `ImageRequest`.
* The WebUI constructs `/v1/images/generations` request bodies in `src/aistudio_api/static/app.js`.
