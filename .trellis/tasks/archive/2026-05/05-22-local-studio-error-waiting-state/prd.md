# Fix Local Studio request error and waiting state

## Goal

Local Studio should handle OpenAI Responses streaming failures more gracefully, especially image-tool streams that can be closed by the upstream before the final response body is complete, and the frontend should make the waiting state obvious while the model is still returning.

## What I already know

* User provided exported request log `C:\Users\bamboo\Downloads\aistudio-requests-1(4).json` showing `/api/local-studio/chat` using `interface_mode=responses`, `stream=true`, `reasoning_effort=high`, and `image_tool_enabled=true`.
* The upstream `/v1/responses` stream returned several `response.*` and `keepalive` SSE events, then failed around `response.image_generation_call.partial_image` with `peer closed connection without sending complete message body (incomplete chunked read)`.
* Current backend records stream errors as assistant error messages and does not save images when `error_message` is set.
* Current Local Studio frontend has `localStudioBusy`, but the chat surface mainly disables controls; the central transcript does not clearly show that it is waiting for model output.

## Requirements

* Preserve a clear error when the upstream stream truly fails.
* If a failing stream already returned usable partial content or image candidates, persist what was received and mark it as incomplete instead of discarding the useful output.
* Parse Responses image partial events where possible.
* Do not render duplicate images when a stream reports a partial image and later reports the same final image; successful streams should prefer final image candidates over progress/partial candidates.
* Improve the Local Studio UI waiting state so users can see that the model request is running, with status text suited to text/image/reasoning work.
* Keep changes focused on Local Studio backend/frontend and regression tests.

## Acceptance Criteria

* [x] A regression test covers Responses stream partial image data followed by a transport failure and verifies the image is persisted with an incomplete/error note.
* [x] A regression test covers Responses stream partial image data followed by final image data and verifies only one image is persisted/rendered.
* [x] A regression test covers Responses stream transport failure without useful output and verifies the error remains visible.
* [x] Static frontend shows an obvious Local Studio pending state while `localStudioBusy` is true.
* [x] `node --check src/aistudio_api/static/app.js` passes after frontend edits.
* [x] Relevant unit tests pass.
* [x] Real WSL API and frontend UI smoke tests pass for non-document code changes.

## Out of Scope

* Replacing the upstream provider or adding a separate `/images/generations` fallback.
* Changing the OpenAI Responses request contract beyond parsing/saving stream output more robustly.
* Hiding genuine upstream failures.

## Technical Notes

* Likely files: `src/aistudio_api/api/routes_local_studio.py`, `src/aistudio_api/infrastructure/local_studio.py`, `src/aistudio_api/static/app.js`, `src/aistudio_api/static/index.html`, `src/aistudio_api/static/style.css`, `tests/unit/test_local_studio.py`.
* Repo memory notes require running `node --check src/aistudio_api/static/app.js` after static JS edits.
