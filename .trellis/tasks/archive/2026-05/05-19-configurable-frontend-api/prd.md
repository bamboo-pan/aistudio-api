# Configurable frontend API selection

## Goal

Make the built-in static frontend more useful as a local testing workbench by letting users choose which API surface each capability exercises, instead of always hard-coding OpenAI-compatible `/v1` endpoints.

## What I already know

* The current frontend is a static Alpine app under `src/aistudio_api/static/`.
* Chat/model/image calls are currently hard-coded to OpenAI-compatible routes:
  * `GET /v1/models`
  * `POST /v1/chat/completions`
  * `POST /v1/images/generations`
  * `POST /v1/images/prompt-optimizations`
* The backend also exposes Gemini-compatible routes under `/v1beta/...` for model listing, count tokens, and generate content.
* The backend does not currently expose a Gemini-native image-generation endpoint equivalent to `/v1/images/generations`; image generation is available through the OpenAI-compatible image route.
* The frontend already persists UI preferences and sessions in `localStorage`.

## Assumptions

* The goal is a testing-oriented UI switch, not a global server configuration change.
* API selection should be per capability so model listing, chat, and image workflows can evolve independently.
* OpenAI-compatible endpoints remain the default to preserve current behavior.

## Requirements

* Add frontend controls that let users choose the API surface used by test workflows.
* Support at least these model-list interfaces:
  * OpenAI compatible: `GET /v1/models`
  * Gemini native: `GET /v1beta/models`
* Support at least these chat interfaces:
  * OpenAI compatible: `POST /v1/chat/completions`
  * Gemini native non-streaming: `POST /v1beta/models/{model}:generateContent`
  * Gemini native streaming: `POST /v1beta/models/{model}:streamGenerateContent`
* Keep image generation configurable in the UI, while only enabling the currently implemented OpenAI image endpoint.
* Convert Gemini model-list responses into the existing frontend model shape so model capability controls continue to work.
* Convert current chat messages and controls into a valid Gemini `generateContent` request when Gemini chat is selected.
* Parse Gemini non-streaming and streaming responses back into the existing transcript display.
* Persist selected API interfaces in browser storage.
* Refresh models and reset incompatible model selections when the model-list interface changes.
* Keep account, rotation, stats, image history, and image-session management on existing project-specific endpoints.

## Acceptance Criteria

* [x] The frontend offers visible API selectors for model list, chat, and image generation workflows.
* [x] Selecting Gemini model list loads models from `/v1beta/models` and still populates the existing model dropdown.
* [x] Selecting Gemini chat sends chat requests to `/v1beta/models/{model}:generateContent` or `:streamGenerateContent` according to the stream toggle.
* [x] Existing OpenAI-compatible behavior remains the default and continues to work.
* [x] Image generation continues to work through `/v1/images/generations`, with unsupported alternatives unavailable rather than silently broken.
* [x] Unit tests cover the static frontend API-selection behavior.
* [x] Relevant existing tests pass.
* [x] Because this touches frontend/API behavior, a WSL real-environment test is attempted per project policy.

## Definition of Done

* Tests added or updated for the frontend API selectors and endpoint routing.
* Lint/typecheck/test commands relevant to the change pass.
* Real-environment test is run where available, or a clear blocker is recorded.
* Task files and code changes are committed on the feature branch.

## Out of Scope

* Adding a new backend Gemini-native image generation endpoint.
* Replacing the static Alpine frontend framework.
* Changing external API contracts for `/v1` or `/v1beta`.
* Changing account rotation or credential storage behavior.

## Technical Notes

* Impacted frontend files are expected to be `src/aistudio_api/static/app.js`, `src/aistudio_api/static/index.html`, and possibly `src/aistudio_api/static/style.css`.
* Existing frontend regression tests live in `tests/unit/test_static_frontend_capabilities.py` and use string assertions against static assets.
* Gemini route implementation is in `src/aistudio_api/api/routes_gemini.py`; OpenAI route implementation is in `src/aistudio_api/api/routes_openai.py`.
