# Fix Responses thinking and complete request logging

## Goal

Fix the OpenAI Responses interface so enabling thinking actually reaches AI Studio and the returned thinking is visible to callers/UI. Expand request logging from only outbound AI Studio requests to a complete, correlated flow covering the client request to the backend, the backend request to AI Studio, the AI Studio response back to the backend, and the backend response to the client.

## What I Already Know

* The frontend Responses mode sends `thinking` in `responsesRequestBody()` when the selected model exposes thinking controls.
* `handle_openai_responses()` maps `payload["thinking"]` into a `ChatRequest`, so the backend path can forward the control to `handle_chat()`.
* The non-streaming Responses conversion currently only emits output text/tool calls and drops `message.thinking` from the chat-compatible response.
* The streaming Responses conversion only maps chat `delta.content` into Responses output text events and ignores chat `delta.thinking`.
* `RequestLogStore.save()` currently stores a single outbound AI Studio request entry; replay and streaming gateway call it before sending the AI Studio request.
* Existing request-log UI can display arbitrary detail JSON, so backend data model changes can surface without a large frontend redesign.

## Requirements

* Responses API must forward thinking levels (`low`, `medium`, `high`) to the AI Studio generation config and keep `off` disabling thinking.
* Non-streaming Responses API must include returned thinking in the Responses-shaped output and in a frontend-readable response field.
* Streaming Responses API must emit thinking deltas from the chat-compatible stream in a stable Responses event shape and include accumulated thinking in the completed response.
* The frontend Responses mode must display thinking for both non-streaming and streaming Responses replies when thinking is present.
* Request logs must include correlated entries for:
  * client request to backend;
  * backend request to AI Studio;
  * AI Studio response to backend;
  * backend response to client.
* Request-log entries for the same external request must share a stable correlation id.
* Existing request-log enable/disable behavior must remain respected.
* Existing request-log routes and current outbound request log behavior must remain backward compatible.

## Acceptance Criteria

* [x] Unit tests prove Responses `thinking: "high"` forwards `enable_thinking=True` and AI Studio thinking config overrides.
* [x] Unit tests prove non-streaming `/v1/responses` returns thinking from the model output.
* [x] Unit tests prove streaming `/v1/responses` emits thinking delta events and a completed response with thinking content.
* [x] Unit tests prove request logging records client request/client response entries and correlates them with outbound AI Studio entries.
* [x] Unit tests prove outbound AI Studio request logs attach upstream response status/body.
* [x] Relevant unit tests pass locally.
* [x] WSL real-environment API and frontend UI testing passes for these code/API/frontend changes.

## Definition of Done

* Tests added or updated for the Responses thinking path and expanded request logging.
* Lint/type or syntax checks pass for edited Python modules.
* Real WSL API and frontend UI verification is performed because the change touches API, browser/gateway, and frontend behavior.
* Task files under `.trellis/tasks/05-19-responses-thinking-full-request-logs/` are committed with the code changes.

## Technical Approach

* Add thinking-aware Responses output helpers so non-streaming output includes a Responses content part for thinking and a top-level `thinking` convenience field for the local UI.
* Extend the streaming Responses bridge to translate chat `delta.thinking` into Responses thinking delta events and carry accumulated thinking into `response.completed`.
* Extend `RequestLogStore` with correlation id, direction/phase metadata, optional status/elapsed metadata, and optional response body parsing while keeping existing request fields and routes intact.
* Use a request-scoped correlation id for inbound API calls so gateway logs created during that request inherit the same id.
* Attach AI Studio response metadata/body to outbound request entries in replay and streaming gateways.
* Add API middleware for `/v1*` and `/v1beta*` routes to log client request and client response bodies when request logging is enabled.

## Decision (ADR-lite)

**Context**: The user asked for the complete flow and explicitly allowed splitting it into several parts. The existing UI already lists individual request log entries and shows full JSON detail.

**Decision**: Preserve the current JSON-file-per-entry store, add `chain_id` for correlation, and save each phase as a separate entry or response attachment instead of replacing the store with a nested trace database.

**Consequences**: This keeps the change small and backward compatible. The UI can immediately inspect the full JSON, while future work can group list entries by `chain_id` if a richer timeline view is desired.

## Out of Scope

* Building a new timeline/grouped request-log UI.
* Logging unrelated static assets, account management calls, or request-log management calls.
* Changing the public shape of existing OpenAI chat completions or Gemini API responses except where needed for Responses thinking visibility.

## Technical Notes

* Likely files: `src/aistudio_api/application/api_service.py`, `src/aistudio_api/infrastructure/request_logs.py`, `src/aistudio_api/infrastructure/gateway/replay.py`, `src/aistudio_api/infrastructure/gateway/streaming.py`, `src/aistudio_api/api/app.py`, `src/aistudio_api/static/app.js`.
* Existing tests to extend: `tests/unit/test_openai_compatibility.py`, `tests/unit/test_request_logs.py`, `tests/unit/test_static_frontend_capabilities.py`.

## Verification Notes

* Unit: `python -m pytest tests/unit -q` -> 267 passed.
* Syntax: `python -m compileall -q src tests/unit` -> passed.
* WSL real API: temporary copy under `/home/bamboo/aistudio-api-realtest-responses-logs`, real accounts copied from `/home/bamboo/aistudio-api/data/accounts`, `/v1/responses` with `thinking: "high"` returned thinking using `gemini-3.1-pro-preview` and request logs contained all four phases with shared `chain_id`.
* WSL real UI: opened `http://127.0.0.1:18094/static/index.html#chat`, selected OpenAI Responses + `gemini-3.1-pro-preview` + Thinking high, sent a prompt, verified the thinking block rendered and `#requests` showed client/upstream/client-response phases plus response body detail.