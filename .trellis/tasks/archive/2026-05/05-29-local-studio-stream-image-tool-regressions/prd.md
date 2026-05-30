# Fix Local Studio Streaming And Image Tool Regressions

## Goal

Fix two Local Studio regressions reported from the real WebUI: enabling Stream currently still appears to deliver the assistant answer only after completion, and Google AI Studio Responses image tool requests can fail with `HTTP 404: Requested entity was not found` when the user asks to turn prior text into an image.

## Requirements

* Local Studio stream mode must expose visible incremental assistant updates in the browser when the upstream path produces streamed chunks.
* The stream route must continue to finish with `local_studio.completed` containing the saved conversation and must not leave pending UI state behind.
* Google AI Studio Responses image-tool requests must use a valid selected Gemini image model and supported image size/options.
* Image generation failures must be surfaced as controlled assistant errors and must preserve request-log lifecycle phases.
* Fixes must not regress provider-aware search/image-tool behavior, reasoning preservation, no-result-cache behavior, or base Playground routes.

## Acceptance Criteria

* [x] Unit/static tests cover the stream delta path and image-tool model/size payload path touched by the fix.
* [x] API smoke verifies a stream request emits at least one `local_studio.delta` before `local_studio.completed` when upstream data is streamed.
* [x] Real WSL API smoke verifies Google Local Studio Responses image-tool generation no longer returns the reported 404 for the selected image model.
* [x] Browser UI smoke verifies streamed text visibly updates before completion and a generated image renders with non-zero natural dimensions.
* [x] Request logs stay redacted and include client/upstream/client lifecycle phases for the tested paths.

## Verification

* `node --check src/aistudio_api/static/app.js` passed.
* Focused unit/static suite passed: `162 passed` for Responses, Local Studio, static frontend, gateway replay, image generation, and request rewriter coverage.
* Full unit suite passed: `370 passed`.
* Real WSL API/UI smoke passed from `/home/bamboo/aistudio-api-stream-image-20260530-232505`: API stream emitted delta before completion, API image tool generated a non-empty asset, request logs recorded expected lifecycle entries, and browser UI rendered streamed text plus image output.

## Definition of Done

* Relevant unit/static tests pass.
* Required WSL real API and UI tests pass for code/API/browser/image-tool changes.
* Task metadata under `.trellis/tasks/05-29-local-studio-stream-image-tool-regressions/` is committed with the code changes.
* Any newly discovered durable convention is considered for `.trellis/spec/` updates.

## Technical Approach

Start by reproducing/inspecting the Local Studio stream frontend/backend chain and the provider-aware image-tool payload construction. Prefer fixing the root contract: stream chunks should flush as SSE deltas through the backend and the frontend should render each delta immediately; image-tool payloads should not send a display label or stale/invalid Gemini image id where the upstream expects a concrete model id.

## Out of Scope

* Redesigning the Local Studio UI layout.
* Adding new providers or new image models beyond repairing the existing Google/OpenAI provider-aware behavior.
* Full exhaustive matrix from `LOCAL_STUDIO_WEB_REAL_SYSTEM_TEST_PLAN.md`; this task runs the focused real smokes required by the touched surfaces.

## Technical Notes

* User screenshot shows `#studio`, Google AI Studio provider, OpenAI Responses interface, `gemini-3.5-flash`, Stream on, Web search on, reasoning high, image tool enabled, and an assistant error: `HTTP 404: [L5,{"Requested entity was not found."}]` after prompt `整理出图片`.
* Relevant backend files identified: `src/aistudio_api/api/routes_local_studio.py`, `src/aistudio_api/infrastructure/local_studio.py`, and `src/aistudio_api/application/api_service.py`.
* Relevant frontend file identified: `src/aistudio_api/static/app.js`.
* Backend quality contract in `.trellis/spec/backend/quality-guidelines.md` already documents Local Studio stream, image-tool, request-log, and real-test obligations.