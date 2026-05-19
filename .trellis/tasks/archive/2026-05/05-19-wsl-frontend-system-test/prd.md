# Restore Frontend Selectors Regression

## Goal

Fix the regression introduced by the previous frontend interface-mode change: the WebUI must show a non-empty interface-mode selector and must expose model-selection entry points on both Playground and image generation pages.

## What I Already Know

* User screenshots show the topbar interface-mode selector rendered with an empty label.
* The Playground no longer exposes a user-facing model selection entry point.
* The image generation page no longer exposes a user-facing image model selection entry point.
* Existing static tests asserted that manual model selectors should not exist, so the prior verification missed the visible UI regression.
* Current frontend files involved are `src/aistudio_api/static/index.html`, `src/aistudio_api/static/app.js`, `src/aistudio_api/static/style.css`, and `tests/unit/test_static_frontend_capabilities.py`.

## Requirements

* The topbar interface-mode selector must display a non-empty label by default and after Alpine initialization.
* Playground must expose a model-selection control for text/chat-capable models.
* Image generation must expose a model-selection control for image-capable models.
* Existing interface-mode routing behavior must continue to work for OpenAI-compatible, Responses, Gemini, and Claude modes.
* Tests must assert the selectors are present and must no longer encode the incorrect assumption that model selectors are forbidden.

## Acceptance Criteria

* [ ] Static unit tests fail if the interface-mode selector can render with an empty label.
* [ ] Static unit tests fail if the Playground model selector entry is removed.
* [ ] Static unit tests fail if the image generation model selector entry is removed.
* [ ] Browser smoke verification confirms the selector labels are visible on `#chat` and `#images`.
* [ ] WSL real-environment smoke passes because this is a frontend/API-facing code change.

## Definition of Done

* Relevant unit/static tests pass.
* Real WSL smoke test passes with real account data available.
* Task files and code changes are committed on the fix branch.

## Out of Scope

* Redesigning the full Playground or image generation layout beyond restoring the lost controls.
* Changing backend model-list or generation semantics unless needed to make the restored controls work.

## Technical Notes

* The existing `.trellis/spec/backend/quality-guidelines.md` contains a stale contract saying model selectors should not be visible; this task may need a spec update after implementation.