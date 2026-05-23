# Local Studio cache, provider, and web_search

## Goal

Upgrade Local Studio so it can use a real Local request cache, let the user switch between multiple saved providers from a dropdown, remember the chosen provider/token, and expose an OpenAI `web_search` toggle alongside the existing `gpt-image-2` tool toggle.

## What I already know

* Local Studio currently stores a single connection object in browser localStorage under `openai.localStudio.settings.v1`.
* The current settings include `baseUrl`, `apiKey`, `timeout`, `interfaceMode`, `model`, stream, reasoning, and image-tool options.
* Local Studio now exposes a provider selector in the settings panel, with connection fields bound to the active provider profile.
* The project has overlapping names that can confuse the mental model: `Local Studio` is the top-level workbench, while `Google AI Studio` is the upstream provider to package underneath it.
* Local Studio now exposes a `web_search` toggle and routes it through the mode-specific payload builders.
* `build_chat_completions_payload`, `build_responses_payload`, `build_gemini_payload`, and `build_claude_payload` map search in mode-specific ways.
* The project already has two distinct cache notions: upstream/provider cache usage (`cached_tokens` / `cachedContentTokenCount`) and in-memory snapshot cache for browser replay/capture.
* The Local Studio Gemini path currently rejects `cachedContent` in browser replay mode elsewhere in the app; Local Studio request caching is therefore implemented as a separate local request/result cache.
* Local Studio conversation files persist messages, usage, images, attachments, model, interface mode, and settings, but not provider profiles.
* Token usage display already normalizes `cached_tokens` / `cachedContentTokenCount` when an upstream response returns them.

## Assumptions (temporary)

* Provider choices will be stored as browser-local saved profiles, not as server-side accounts.
* A provider profile will own at least `name`, `baseUrl`, `apiKey`, `timeout`, and `interfaceMode`.
* Selecting a provider will load its saved token and settings back into the Local Studio form.
* Local Studio cache support is implemented as a local request/result cache that is separate from provider usage accounting and snapshot cache.

## Open Questions

* Provider-native cache primitives such as Gemini `cachedContent` remain a possible future layer, but are not part of this implementation.

## Requirements (evolving)

* Normalize project terminology so `Local Studio`, `Google AI Studio provider`, `upstream/provider cache`, and `snapshot cache` are clearly distinct in UI and code paths.
* Add a provider dropdown in Local Studio.
* Allow multiple saved providers to be chosen independently.
* Remember the active provider and its token across reloads.
* Keep the current Local Studio connection fields, but bind them to the selected provider profile.
* Add a Local Studio web_search toggle, similar to the existing `gpt-image-2` toggle.
* Make the new toggle feed the existing Local Studio payload builders so the upstream request carries search when enabled.
* Add true Local request-cache support for Local Studio, keyed by provider, token, interface mode, model, request body, and namespace.
* Keep token usage display intact, including cached token metrics when the upstream returns them.

## Acceptance Criteria (evolving)

* [x] Project terminology is internally consistent: Local Studio is the workbench, Google AI Studio is a provider, and cache terms are separated by layer.
* [x] Local Studio can switch between saved provider profiles without losing the previously saved token for each profile.
* [x] Refreshing the page restores the last active provider profile.
* [x] The Local Studio request body still routes through the correct mode-specific payload builder after provider switching.
* [x] The Local Studio UI includes a `web_search` enable/disable control, and turning it on adds the corresponding upstream search field/tool.
* [x] Cache support is real and provider-aware, not just a UI-only label.
* [x] Existing Local Studio chat, stream, model loading, and token display behavior continues to work in focused tests.

## Definition of Done

* Focused tests added or updated for provider UI contracts, `web_search`, and cache behavior.
* Frontend syntax validated after editing `src/aistudio_api/static/app.js`.
* Real API and UI smoke tests passed with credentials.
* Documentation updated when the user-facing behavior changes.

## Verification

* `node --check src/aistudio_api/static/app.js` passed.
* Focused unit/static tests passed: `39 passed`.
* Full unit suite passed: `310 passed`.
* WSL real API smoke passed for health, request logs, model loading, non-stream cache miss/hit, and stream cache miss/hit.
* Browser UI smoke passed for `#studio`: provider profile injection, model loading, Local request cache toggle, `web_search` control presence, message send, draft clear, assistant render, and usage render.

## Out of Scope

* Server-side provider administration UI.
* Migrating provider profiles into the account system.
* Reworking unrelated Playground chat behavior unless it is needed to share the search contract.

## Technical Notes

* Local Studio frontend lives in `src/aistudio_api/static/app.js` and `src/aistudio_api/static/index.html`.
* Local Studio API lives in `src/aistudio_api/api/routes_local_studio.py`.
* Payload helpers and persistence live in `src/aistudio_api/infrastructure/local_studio.py`.
* Existing search behavior in Playground can be reused as the contract reference for the new Local Studio toggle.
* The current Local Studio token display already reads `cached_tokens` from normalized usage.
* Snapshot cache is an internal browser replay/cache boundary and should not be conflated with provider-native cached token accounting.

## Research References

* [`research/terminology-map.md`](research/terminology-map.md) — vocabulary and naming split between workbench, provider, and cache layers.
* [`research/provider-layering.md`](research/provider-layering.md) — proposed provider/profile/capability layering for Local Studio.
* [`research/cache-boundaries.md`](research/cache-boundaries.md) — cache layer separation and current code boundaries.