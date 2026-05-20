# Fix Dynamic Model List Refresh

## Goal

Model lists exposed by the API and shown in the frontend should refresh when supported AI Studio models change, instead of leaving users stuck with the initial stale dropdown. The immediate regression is that AI Studio shows `gemini-3.5-flash`, while the local dropdown still stops at older registered models.

## What I Already Know

* The frontend calls `loadModels()` at startup and consumes `/v1/models` for OpenAI/Responses/Claude modes or `/v1beta/models` for Gemini mode.
* Both model list endpoints are currently derived from the static `MODEL_CAPABILITIES` registry.
* Unknown models can be inferred in non-strict paths, but model metadata lookup and several request validation paths require registered capabilities.
* The UI currently has no visible refresh action or loading state for the model selector.

## Requirements

* Include the newly available `gemini-3.5-flash` model in API model metadata and frontend model dropdowns.
* Add a user-facing refresh control for model lists so users can reload the current interface mode's models without a full page reload.
* Keep model selection valid after a refresh: preserve the current model when it still exists, otherwise choose a valid text model.
* Surface loading/failure state without breaking existing chat, image, and prompt optimizer defaults.
* Preserve static registry fallback behavior; do not block normal model listing on live browser/UI scraping.

## Acceptance Criteria

* [x] `/v1/models` includes `gemini-3.5-flash` with text model capabilities.
* [x] `/v1beta/models` includes `models/gemini-3.5-flash` with generation methods.
* [x] The frontend exposes a refresh button near model selectors and calls `loadModels()` on demand.
* [x] Unit/static tests cover the new model and refresh UI behavior.
* [x] Existing model capability, API compatibility, and frontend tests pass.

## Out of Scope

* Full browser scraping of the AI Studio public model catalog.
* Account-tier-specific model availability filtering.
* Changing request wire format or capture/replay behavior.

## Technical Notes

* Relevant code: `src/aistudio_api/domain/model_capabilities.py`, `src/aistudio_api/application/api_service.py`, `src/aistudio_api/static/app.js`, `src/aistudio_api/static/index.html`.
* Relevant tests: `tests/unit/test_model_capabilities.py`, `tests/unit/test_gemini_native_routes.py`, `tests/unit/test_static_frontend_capabilities.py`.
