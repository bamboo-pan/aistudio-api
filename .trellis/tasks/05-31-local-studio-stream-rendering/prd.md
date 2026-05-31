# Fix Local Studio Streaming Rendering

## Goal

Fix the Local Studio streamed-response path so assistant text/progress appears incrementally while the request is running instead of appearing all at once after the waiting timer ends.

## What I Already Know

* User reproduced the issue in the browser UI: streamed output is displayed only after the timer finishes, not incrementally.
* The issue affects both built-in Google/Gemini-backed Local Studio requests and custom OpenAI-compatible providers.
* The current frontend reads `/api/local-studio/chat` with `response.body.getReader()` and updates the active assistant message on `local_studio.delta` events.
* The Local Studio backend wraps upstream stream chunks into `local_studio.delta` events and emits a final `local_studio.completed` event.
* Backend spec requires streamed Local Studio responses to emit incremental `local_studio.delta` chunks before completion when upstream chunks arrive.

## Requirements

* Preserve Local Studio stream mode for Gemini, OpenAI Chat, OpenAI Responses, and Claude-compatible interface modes.
* Emit browser-visible `local_studio.delta` events as soon as upstream stream chunks contain user-visible content, reasoning, tool progress, usage, or error data.
* Keep the final `local_studio.completed` event with the saved conversation and no token leakage.
* Do not reintroduce Local Studio result caching or image-tool `/images/generations` fallback.
* Keep the static UI consuming the same `local_studio.delta` / `local_studio.completed` contract unless a frontend bug is proven.

## Acceptance Criteria

* [x] Unit/static tests cover the Local Studio stream renderer contract and existing Local Studio stream behavior.
* [x] Existing Local Studio image-tool, reasoning, partial image, and error persistence tests continue to pass.
* [x] Static frontend syntax check passes if `src/aistudio_api/static/app.js` changes.
* [x] Real WSL API smoke verifies Local Studio stream emits incremental deltas before completion.
* [x] Real browser UI smoke verifies streamed text/progress appears while the request is still busy.

## Definition of Done

* Relevant unit tests pass.
* API-level real environment smoke passes.
* Frontend UI real smoke passes.
* Any new durable stream-contract knowledge is captured in `.trellis/spec/` if needed.
* Task files are committed with the code changes.

## Technical Approach

Trace the Local Studio stream path from frontend fetch reader to `routes_local_studio._stream_local_studio_chat`, reproduce the buffering behavior with a slow upstream stream, then fix the layer that delays delta emission. Prefer a backend fix if the frontend already receives no early bytes; prefer a minimal frontend refresh fix if early bytes are received but Alpine does not repaint.

## Out of Scope

* Redesigning the Local Studio UI.
* Changing provider profile storage or token handling.
* Adding new Local Studio interface modes.
* Changing non-stream response semantics.

## Technical Notes

* Main files inspected: `src/aistudio_api/api/routes_local_studio.py`, `src/aistudio_api/infrastructure/local_studio.py`, `src/aistudio_api/static/app.js`, `src/aistudio_api/static/index.html`, and `tests/unit/test_local_studio.py`.
* Relevant spec: `.trellis/spec/backend/quality-guidelines.md` Local Studio scenario, especially stream delta and real smoke requirements.

## Verification Results

* `node --check src/aistudio_api/static/app.js`: passed.
* `python -m pytest tests/unit/test_static_frontend_capabilities.py tests/unit/test_local_studio.py`: 57 passed.
* `wsl.exe -d Ubuntu-24.04 -- bash .trellis/tasks/05-31-local-studio-stream-rendering/verification/wsl_real_stream_rendering_smoke.sh`: passed. API first delta arrived at 2.425s before completion chunk 254; browser DOM first showed stream output at 2.315s while Local Studio was still busy.