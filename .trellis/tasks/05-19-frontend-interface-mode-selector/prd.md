# Fix frontend interface mode selector

## Goal

The built-in WebUI should expose a complete interface-mode selector instead of separate and incomplete API/model selectors. Playground and the image generation page must each show a single interface-mode dropdown with the four supported text client modes: OpenAI compatible, OpenAI Responses, Gemini, and Claude. Model selection should be internal and automatic.

## Requirements

* Replace the existing topbar model picker plus separate model/chat/image API pickers with one visible interface-mode dropdown for user-facing work pages.
* The dropdown options must be exactly the four supported interface modes:
  * OpenAI compatible, mapped to `/v1/chat/completions` for Playground chat.
  * OpenAI Responses, mapped to `/v1/responses` for Playground chat.
  * Gemini, mapped to `/v1beta/models/{model}:generateContent` or `:streamGenerateContent` for Playground chat.
  * Claude, mapped to `/v1/messages` for Playground chat.
* Playground must not expose a model selection dropdown. It should automatically use a valid text model from the current mode's model list.
* Image generation must not expose a model selection dropdown. It should automatically use a valid image model from the current model list.
* The image generation page must expose the same interface-mode selector entry as Playground. Image generation remains routed through the existing image generation backend contract while prompt optimization/text helper behavior follows the selected mode where applicable.
* Existing capability-driven controls, chat sessions, prompt optimizer, image session history, and runtime stats must continue working.
* Existing localStorage preferences should migrate safely. Invalid or old partial API selections should fall back to OpenAI compatible.

## Acceptance Criteria

* [x] `app.js` defines and validates the four interface modes in one place.
* [x] Playground topbar shows only the interface-mode dropdown and no model picker.
* [x] Image generation page shows only the interface-mode dropdown and no image-model picker.
* [x] Playground requests route correctly for all four modes.
* [x] Automatic model defaults keep chat send, prompt optimization, and image generation usable without user model selection.
* [x] Static frontend tests cover the four interface options, removed model selectors, and routing functions.
* [x] Relevant unit tests pass.
* [x] WSL real-environment validation passes for the built-in frontend and the four selectable modes.

## Validation Notes

* Windows focused regression: `34 passed` for static frontend plus OpenAI/Gemini route tests.
* Windows full unit suite: `249 passed`.
* Post-merge static frontend check: `12 passed`.
* WSL focused static frontend check after final patch sync: `12 passed`.
* WSL real-environment smoke served the built-in frontend, verified Playground and image-generation selectors, and received HTTP 200 from OpenAI compatible, OpenAI Responses, Gemini, Claude, and image generation requests.

## Definition of Done

* Code is minimal and consistent with the existing Alpine/static frontend style.
* Lint/type/test checks relevant to this change are green.
* Real WSL validation uses a temporary directory under `/home/bamboo` and the real account credential directory specified by the project instructions.
* Task files and implementation are committed together before finish-work.

## Technical Approach

Unify the current `modelApi`, `chatApi`, and `imageApi` state into a single interface mode state used by the visible selector. Keep internal automatic model discovery by fetching `/v1/models` for OpenAI-compatible, Responses, and Claude modes, and `/v1beta/models` for Gemini mode. Add request builders/parsers for Responses and Claude using the backend's existing `/v1/responses` and `/v1/messages` routes. Leave the image generation API contract on `/v1/images/generations`, because that is the existing backend image contract, but remove the model dropdown and auto-select the first available image model.

## Decision (ADR-lite)

**Context**: The backend already exposes all four text-compatible interfaces, but the WebUI currently exposes separate incomplete API selectors and model pickers.

**Decision**: Use one user-facing `interfaceMode` dropdown with four modes and keep model choice internal.

**Consequences**: The UI becomes simpler and matches external client interface modes. Some advanced manual model selection is intentionally removed from this task to satisfy the requested built-in frontend behavior.

## Out of Scope

* Adding new backend API routes.
* Changing model capability metadata.
* Replacing the image generation backend contract with non-image-specific text routes.
* Adding a separate advanced/manual model picker.

## Technical Notes

* Existing frontend files are `src/aistudio_api/static/app.js`, `src/aistudio_api/static/index.html`, and `src/aistudio_api/static/style.css`.
* Existing backend routes already include `/v1/chat/completions`, `/v1/responses`, `/v1/messages`, `/v1/models`, `/v1/images/generations`, and Gemini `/v1beta` routes.
* Existing static tests live in `tests/unit/test_static_frontend_capabilities.py`.