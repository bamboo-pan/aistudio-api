# Fix OpenAI Provider Search Tool

## Goal

Fix Local Studio Responses mode so custom OpenAI-compatible providers send the provider-supported search tool type instead of the Google/internal Responses compatibility search tool type, then update the real system test plan and verify the bug with focused tests plus real WSL API/UI checks where feasible.

## Requirements

* Local Studio OpenAI-compatible providers in Responses mode with `search=true` must send `{"type":"web_search"}` in the `/responses` tools list.
* Local Studio built-in Google AI Studio provider in Responses mode with `search=true` must keep sending `{"type":"web_search_preview"}` for the internal compatibility route.
* Search and image tool ordering/compatibility must remain stable when both tools are enabled.
* The chat route must preserve provider type before building the upstream payload, including stream and non-stream paths.
* The real system test plan must explicitly cover the reported bug: OpenAI-compatible provider search must not send `web_search_preview` and must not surface `HTTP 400: Unsupported tool type: web_search_preview`.
* If tests expose additional bugs in this scope, fix them and rerun the relevant tests until passing.

## Acceptance Criteria

* [ ] Unit tests prove OpenAI-compatible Responses search uses `web_search`.
* [ ] Unit tests prove Google AI Studio Responses search still uses `web_search_preview`.
* [ ] Unit/API tests prove `/api/local-studio/chat` forwards provider-aware search tools for custom OpenAI providers.
* [ ] `LOCAL_STUDIO_WEB_REAL_SYSTEM_TEST_PLAN.md` names the new regression oracle.
* [ ] Focused Local Studio/OpenAI compatibility tests pass.
* [ ] WSL real API/UI smoke is attempted with real credentials; any unavailable dependency is documented with the exact blocker.
* [ ] Backend spec is updated if the provider-aware search contract changed from the stored spec.

## Definition of Done

* Code is minimal and consistent with existing Local Studio helpers.
* Tests are added/updated at the lowest reliable level and rerun after fixes.
* No raw OpenAI key, Google cookie, Authorization header, request-log export, or generated asset is committed.
* Task artifacts under `.trellis/tasks/05-24-openai-provider-search-tool/` are committed with the code change.

## Technical Approach

Thread the resolved provider kind into Local Studio payload construction. Keep provider-specific tool decisions inside `build_responses_payload` so the route only supplies context and image/search tool behavior remains centralized.

## Decision (ADR-lite)

**Context**: Local Studio uses one Responses interface for both the built-in Google AI Studio compatibility route and arbitrary OpenAI-compatible providers. The previous payload builder treated all Responses search requests as Google/internal search and emitted `web_search_preview`.

**Decision**: Make Responses search tool selection provider-aware: `google-ai-studio` keeps `web_search_preview`; `openai` uses `web_search`.

**Consequences**: Existing Google paths remain unchanged while OpenAI-compatible providers avoid the unsupported tool error. Future provider-specific tools should be selected through the same provider-aware options path.

## Out of Scope

* Redesigning the full Local Studio provider UI.
* Changing baseline Playground search behavior outside Local Studio.
* Adding new provider types beyond the existing `google-ai-studio` and `openai` kinds.

## Technical Notes

* Impacted implementation: `src/aistudio_api/infrastructure/local_studio.py`, `src/aistudio_api/api/routes_local_studio.py`.
* Focused tests: `tests/unit/test_local_studio.py`, `tests/unit/test_openai_compatibility.py`.
* Existing backend spec currently says Responses search always uses `web_search_preview`; this task should update it to provider-aware behavior.