# Local Studio provider management and tool support

## Goal

Turn Local Studio into the higher-level workspace for provider selection, model loading, conversation control, and tool toggles. Google AI Studio should be the built-in default provider with no URL/token setup, while custom OpenAI providers remain configurable with URL and token fields. The Local Studio experience should support chat, search, and image generation combinations through provider-backed tools, with request cache enabled by default and shared runtime controls kept consistent.

## What I already know

* The existing app already has a Local Studio page, provider list state, model loading, conversation persistence, request cache, and stream handling in `src/aistudio_api/static/app.js` and `src/aistudio_api/api/routes_local_studio.py`.
* The current Local Studio provider model still treats provider setup as an editable base URL / API token record, which makes the built-in Google AI Studio path too similar to custom providers.
* The current UI already exposes stream, reasoning, search, cache, interface mode, model, and image tool controls, but the provider model and tool model are still mixed together.
* Google AI Studio needs to be the default provider without requiring a base URL or token because the project ships with that capability already.
* Custom OpenAI providers should continue to require URL + token, and they should expose search and image tool toggles in Local Studio.
* Cache should be on by default, without a manual on/off switch.
* The existing repo already has Google Search and gpt-image-2 plumbing, including image-generation payload support and response image persistence.

## Research References

* [`../../../../.trellis/spec/backend/index.md`](../../../../.trellis/spec/backend/index.md) — backend scope and quality entry point for this task.
* [`../../../../.trellis/spec/backend/quality-guidelines.md`](../../../../.trellis/spec/backend/quality-guidelines.md) — current backend quality and Local Studio contract notes.
* [`../../../../.trellis/spec/backend/error-handling.md`](../../../../.trellis/spec/backend/error-handling.md) — useful for request validation and upstream failure handling.
* [`../../../../.trellis/spec/backend/directory-structure.md`](../../../../.trellis/spec/backend/directory-structure.md) — useful for keeping Local Studio logic in the existing module layout.
* [`../../../../.trellis/spec/backend/logging-guidelines.md`](../../../../.trellis/spec/backend/logging-guidelines.md) — useful for request-log and secret-redaction behavior.
* [`../../../../.trellis/spec/guides/index.md`](../../../../.trellis/spec/guides/index.md) — shared thinking guide index for cross-layer and reuse decisions.
* [`../../../../.trellis/spec/guides/cross-layer-thinking-guide.md`](../../../../.trellis/spec/guides/cross-layer-thinking-guide.md) — relevant because this task spans backend, persisted settings, and the static UI.
* [`../../../../.trellis/spec/guides/code-reuse-thinking-guide.md`](../../../../.trellis/spec/guides/code-reuse-thinking-guide.md) — relevant because provider/tool defaults and model capability constants are easy to duplicate incorrectly.

## Assumptions (temporary)

* Google AI Studio will be represented as a built-in provider profile in the browser settings, but its runtime credentials will still be derived from the project defaults rather than user-entered URL/token fields.
* OpenAI-compatible custom providers will remain browser-local profiles stored in `openai.localStudio.settings.v1`.
* Local Studio will continue to use the existing `/api/local-studio/*` backend routes instead of introducing a separate provider management API.
* Search and image toggles will be modeled as tool toggles on the provider-backed Local Studio flow, not as separate product pages.

## Open Questions

* None blocking; the requested direction is clear enough to implement directly.

## Requirements (evolving)

* Local Studio defaults to a built-in Google AI Studio provider.
* The built-in Google AI Studio provider does not require manual URL or token configuration.
* Custom OpenAI providers require base URL and token.
* Provider management must let the user add, select, edit, and keep provider profiles.
* Request cache is enabled by default.
* Shared runtime controls remain available: stream, reasoning level, model capabilities, timeout, interface mode, and model selection.
* Search and image toggles are provider-backed tool switches.
* Image generation must be wrapped as a tool when enabled.
* Google AI Studio supports Google Search and Google image tool toggles.
* OpenAI providers support OpenAI search and OpenAI image tool toggles.
* Local Studio should remain the higher-level entry point for the chat/search/image composition that used to be split across Playground and image generation.

## Acceptance Criteria (evolving)

* [ ] Local Studio loads with Google AI Studio as the default provider.
* [ ] The built-in Google AI Studio provider does not require user-entered base URL or token fields.
* [ ] Custom OpenAI providers require base URL and token validation before model loading or chat.
* [ ] Provider management supports adding and switching provider profiles from the Local Studio UI.
* [ ] Cache is enabled by default and persisted as an always-on Local Studio setting.
* [ ] Local Studio exposes search and image tool toggles per provider/interface combination.
* [ ] Image generation is sent as a tool-enabled request path rather than a separate special-case flow.
* [ ] The UI keeps stream, reasoning, model, timeout, interface, and model selection as shared controls.
* [ ] Existing Playground and image-generation functionality still work through the provider-backed model after the change.
* [ ] Tests cover provider defaults, validation, tool toggle behavior, and the revised Local Studio settings flow.

## Definition of Done

* Tests added or updated for the changed behavior.
* Backend and frontend checks pass.
* Local Studio real-use smoke test passes in the WSL environment for API and browser UI flows.
* Documentation/spec notes updated if behavior changes.

## Out of Scope

* Redesigning unrelated chat, account, or request-log workflows.
* Introducing a new standalone provider backend service.
* Replacing the existing Google AI Studio / OpenAI compatibility layers outside the Local Studio experience.

## Technical Notes

* Main touch points: `src/aistudio_api/api/routes_local_studio.py`, `src/aistudio_api/infrastructure/local_studio.py`, `src/aistudio_api/static/app.js`, and `src/aistudio_api/static/index.html`.
* Provider storage currently lives in browser local storage under `openai.localStudio.settings.v1`.
* Cache keys already include base URL, token hash, interface mode, model, provider id/name, namespace, and request shape without `stream`.
* The Local Studio flow already persists conversations and generated assets in the backend store.