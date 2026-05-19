# Fix Responses output_text history input

## Goal

Allow the server-side OpenAI Responses compatibility endpoint to accept assistant history messages whose content blocks are copied from prior Responses output items. Clients may send `output_text` blocks from a previous `/v1/responses` response back in the next request's `input`; the proxy should treat them as text history instead of rejecting the request locally.

## Requirements

* `/v1/responses` must accept message content blocks with `type: "output_text"` when normalizing input history.
* `output_text` blocks must be converted to the same internal text representation as `text` and `input_text` blocks.
* Existing support for `text`, `input_text`, image, file, tool result, and tool use blocks must remain unchanged.
* Unsupported block types must still fail with a clear OpenAI-compatible 400 error.

## Acceptance Criteria

* [x] A request shaped like the captured failing log, with an assistant history message containing `output_text`, returns 200 instead of local 400 when the downstream client succeeds.
* [x] The normalized message passed to the chat path contains the assistant text as a normal text content block.
* [x] Existing OpenAI compatibility tests continue to pass.

## Verification

* `python -m pytest tests/unit/test_openai_compatibility.py` — 20 passed.
* `python -m pytest` — 270 passed.
* WSL real API smoke from `/home/bamboo/aistudio-api-realtest-output-text` using `/home/bamboo/aistudio-api/data/accounts` — `/v1/responses` with assistant `output_text` history returned 200.
* WSL real frontend smoke on `http://127.0.0.1:18127/static/index.html` — OpenAI Responses mode sent a request and rendered the assistant reply.

## Definition of Done

* Unit tests cover the new `output_text` history input case.
* Relevant backend compatibility tests pass locally.
* Because this changes an API compatibility boundary, WSL real API/UI smoke is attempted according to project policy.
* Task files and code changes are committed together on the feature branch.

## Technical Approach

Extend the shared content-block coercion boundary used by Responses input conversion so `output_text` is accepted together with `text` and `input_text`. This keeps the compatibility behavior centralized and avoids special-casing only one route branch.

## Decision (ADR-lite)

**Context**: Responses clients often preserve previous assistant output as Responses message/output items, where textual content uses `output_text`. Replaying that transcript into the next `input` currently fails before reaching AI Studio.

**Decision**: Treat `output_text` as textual input history at the server conversion boundary.

**Consequences**: The endpoint becomes more tolerant of common Responses transcript replay patterns while preserving rejection of truly unknown block types.

## Out of Scope

* Full hosted OpenAI Responses state management, background tasks, or remote tool parity.
* Frontend transcript serialization changes; this task fixes the server compatibility boundary.

## Technical Notes

* Failure observed in request log: `unsupported content block type: output_text` from local `/v1/responses` parsing.
* Relevant code: `src/aistudio_api/application/api_service.py` `_coerce_openai_content_blocks()` and `_messages_from_responses_payload()`.
* Relevant tests: `tests/unit/test_openai_compatibility.py`.
* Relevant spec: `.trellis/spec/backend/quality-guidelines.md` scenario "Client-Compatible Chat/Responses/Messages Gateway".