# Reimplement OpenAI Local Studio

## Goal

Undo the incorrect previous GPT image prompt workbench implementation and rebuild the requested OpenAI Responses API local chat/image workbench inside this repository's existing FastAPI + static Alpine-style frontend. The resulting page should be recognizable as `OpenAI Local Studio`: a three-column local workbench for connecting to OpenAI or OpenAI-compatible `/v1` APIs, chatting through the Responses API, managing conversations, uploading attachments, and using an image generation tool configured around `gpt-image-2`.

## What I Already Know

- The previous commit `9e1b07e Add GPT image prompt workbench` was wrong and must be reverted before reimplementation.
- The source project summary describes a Node/Express app named `openai-responses-chat`, but this repo is `aistudio-api`, a Python/FastAPI package with a plain HTML/CSS/JS frontend.
- Existing UI lives in `src/aistudio_api/static/index.html`, `app.js`, and `style.css`.
- Existing API routes already expose AI Studio-compatible `/v1/models`, `/v1/responses`, `/v1/images/generations`, image sessions, generated images, request logs, and account management.
- The new feature should not reintroduce the incorrect GPT image prompt subpage.

## Requirements

- Add an `OpenAI Local Studio` workbench entry to the existing web UI.
- Keep the frontend plain HTML/CSS/JS with the existing Alpine-style app structure; do not add React/Vite/Express.
- Let users configure an OpenAI-compatible `/v1` base URL and API token from the browser UI.
- Load models from the configured endpoint and filter out image-only and specialist non-chat models such as `gpt-image-*`, audio, realtime, TTS, transcription, and embedding models from the conversation model list.
- Provide a three-column workbench layout: conversation history, central chat transcript/composer, and connection/model/image settings.
- Support creating, restoring, renaming, deleting, and bulk deleting local conversations.
- Persist local conversations and uploaded/generated assets on the server side rather than only in browser localStorage.
- Support text, image, PDF, JSON, and text-like file attachments in chat input.
- Send chat through the OpenAI Responses API style request to the configured compatible endpoint.
- When the `gpt-image-2` image tool is enabled and a compatible endpoint does not support Responses image tools, fall back to the OpenAI Images API shape at `/images/generations` with the same prompt and image options.
- Support reasoning effort and summary settings, and display reasoning/thinking summaries when returned.
- Include image generation tool controls with fixed model `gpt-image-2`, size, quality, background, format, and compression fields.
- Populate the `gpt-image-2` size controls from the official prompting guide: support the common valid sizes `1024x1024`, `1024x1536`, `1536x1024`, `1536x864`, `2560x1440`, and near-4K `3824x2144`; do not advertise invalid `3840x2160` as the default 4K option because the model requires maximum edge length to be less than `3840px`.
- Validate `gpt-image-2` custom sizes before sending them upstream: both edges multiples of 16, longest edge less than 3840, ratio no greater than 3:1, total pixels between 655,360 and 8,294,400.
- Allow rerunning from a selected user turn or the assistant turn after it by truncating later messages and resubmitting the selected user input.
- Save generated image outputs under local storage and expose them back to the UI.
- Surface upstream timeout/errors clearly, including HTTP 524-style failures.
- Use the real OpenAI key from `C:\Users\bamboo\Desktop\GPT_image\key.txt` for final end-to-end testing without storing or printing the key.

## Acceptance Criteria

- [ ] The previous incorrect commit is reverted on the feature branch.
- [ ] A user can open the new workbench from the sidebar and see title text `OpenAI Local Studio`.
- [ ] The workbench can save connection settings locally in the browser and request model loading through the backend.
- [ ] `POST /api/local-studio/models` fetches compatible model lists and excludes `gpt-image-*` plus obvious specialist non-chat models from chat model choices.
- [ ] Server-side conversation CRUD endpoints exist for list/create/read/update/delete/bulk-delete.
- [ ] `POST /api/local-studio/chat` records a user message, calls the configured Responses API endpoint, stores the assistant response, and returns the updated conversation.
- [ ] Chat request payloads include text plus supported attachment content where practical.
- [ ] Image tool configuration is available in the UI and can be sent as a Responses API image_generation tool definition.
- [ ] Image tool generation can fall back to `/images/generations` when the configured compatible endpoint rejects the Responses image-generation tool.
- [ ] The image tool exposes official `gpt-image-2` common sizes and includes guidance that sizes above `2560x1440` are experimental.
- [ ] Invalid `gpt-image-2` sizes fail locally with a clear validation error before the upstream request.
- [ ] Rerun from a previous turn truncates subsequent messages and stores the new assistant result.
- [ ] Unit tests cover model filtering, conversation CRUD, and request payload construction/error handling.
- [ ] Static frontend tests cover the new sidebar/workbench controls and model filtering affordance.
- [ ] A real-key API/UI smoke test confirms `gpt-image-2` image tool generation succeeds with one of the newly exposed sizes.

## Definition of Done

- Tests added or updated for backend and static frontend behavior.
- `node --check src/aistudio_api/static/app.js` passes after JS edits.
- Relevant `pytest` tests pass.
- Because this task changes code/API/frontend, WSL real environment API and UI tests are run before final commit, per project instructions.
- Because the user supplied a real OpenAI key path for this update, include one final real-key test that reads the key from disk only at runtime and verifies a generated image is persisted locally.
- Task files under `.trellis/tasks/05-21-reimplement-openai-local-studio/` are committed with the implementation.

## Out of Scope

- Reintroducing the previous GPT image prompt workbench/subpage.
- Adding a separate Express server, Node package, or new build pipeline.
- Implementing every possible OpenAI Responses streaming event type in the first version.
- Storing real API credentials in the repository.

## Research References

- `research/architecture-fit.md` — explains why the implementation should be adapted into the existing FastAPI/static frontend architecture.
- `research/gpt-image-2-sizes.md` — records the official `gpt-image-2` size constraints and chosen UI options.

## Technical Notes

- Expected backend additions likely belong under `src/aistudio_api/api/` for routes and `src/aistudio_api/infrastructure/` for local file/conversation storage.
- Existing app registration happens in `src/aistudio_api/api/app.py`.
- Existing static tests live in `tests/unit/test_static_frontend_capabilities.py`.
