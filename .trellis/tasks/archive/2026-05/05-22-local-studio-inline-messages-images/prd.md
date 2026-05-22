# Fix Local Studio Inline Messages and Image Display

## Goal

Fix the OpenAI Local Studio chat UI so sent user messages appear immediately in the transcript, and generated images from Responses streaming are saved and rendered in the conversation instead of leaving the assistant message as text-only or `(no response content)`.

## What I Already Know

- The user observed that the exported request log is large, but the likely visible failure is only that images do not display.
- The user also observed Local Studio only shows the sent user message after an assistant response arrives.
- Playground already pushes the user message into `msgs` before awaiting the backend; Local Studio currently clears draft/files and waits for the backend conversation.
- `C:\Users\bamboo\Downloads\aistudio-requests-1(3).json` has one Local Studio request group. The upstream streamed response is about 6.18 MB, while the final client response is about 2 KB.
- Current Local Studio stream backend accumulates content/thinking/usage, but does not save image candidates from stream events into the assistant message.

## Requirements

- Local Studio non-rerun sends must insert a user message into the current conversation immediately after the send is accepted by the UI.
- The optimistic user message must include the text and attachment previews already selected in the composer.
- On successful non-stream or stream completion, the frontend must replace/reconcile the optimistic conversation with the saved backend conversation.
- On request failure, non-rerun sends must restore the draft and selected files so the user can retry.
- Local Studio streaming must collect image candidates and persist saved image asset URLs in the final assistant message.
- Local Studio Responses image-tool sends must not fall back to `/images/generations`; HTTP/transport failures surface as upstream errors, and completed responses without image candidates stay image-less.
- Local Studio image rendering must use valid URLs for saved assets and be tolerant of image objects containing `url`, `path`, `data_url`, `b64_json`, `b64`, or `result`.
- Include the user's updated `AGENTS.md` in the final commit as requested.

## Acceptance Criteria

- [ ] Sending a Local Studio message immediately shows the user bubble before any assistant response arrives.
- [ ] A streamed Local Studio image generation response produces an assistant message with rendered image thumbnails whose URLs load successfully.
- [ ] Local Studio image-tool failures or no-candidate completions do not call `/images/generations`.
- [ ] If a Local Studio request fails, the draft and attached files are restored.
- [ ] Existing Playground behavior is unchanged.
- [ ] Static checks and relevant unit tests pass.
- [ ] WSL real API and browser UI smoke tests are run for Local Studio send and image rendering.

## Out of Scope

- Redesigning the Local Studio layout.
- Changing provider routing or image model validation rules beyond the stream image persistence bug.
- Importing the large downloaded request log into repository fixtures.

## Technical Notes

- Static frontend: `src/aistudio_api/static/app.js`, `src/aistudio_api/static/index.html`.
- Backend Local Studio stream persistence: `src/aistudio_api/api/routes_local_studio.py`, `src/aistudio_api/infrastructure/local_studio.py`.
- Spec contract: `.trellis/spec/backend/quality-guidelines.md` scenario "OpenAI Local Studio API, Interface Modes, and Image Tool".
- Research: `research/request-log-image-rendering.md`.
