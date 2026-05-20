# Fix IDE tool call handling

## Goal

Fix `/v1/responses` tool-call behavior observed from a programming IDE using this proxy as an OpenAI Responses-compatible endpoint. The captured request at `C:\Users\bamboo\Downloads\aistudio-requests-1.json` shows Cursor-style Responses input with tool history and tool declarations; the proxy returned streamed text shaped like `Tool call requested: Shell {...}` instead of a Responses function-call item/event, so the IDE could not execute the requested tool.

## What I already know

* The user is invoking the model from a programming IDE and provided a request-log export for the failing exchange.
* The request is `POST /v1/responses`, `stream: true`, model `gemini-3.5-flash`.
* The request input contains 5 completed `function_call` items and 5 matching `function_call_output` items.
* The request tools array contains flat Responses-style function tools such as `Shell`, `Read`, `Write`, and others.
* The backend converted the tool declarations into the AI Studio wire `tools` field; the real upstream response still streamed ordinary text beginning with `Tool call requested: Shell {...}`.
* Current backend specs intentionally keep Responses tool-continuation history as text for real AI Studio compatibility; this task should not switch replayed tool results to structured `functionResponse` without real proof.

## Requirements

* Preserve existing `/v1/responses` support for prior `function_call` / `function_call_output` history.
* When tools are present and the upstream text response exactly represents a tool request in the compatibility text shape, return it to the client as a Responses `function_call` output item instead of normal assistant text.
* Streaming `/v1/responses` must emit tool-call output events that IDE clients can consume.
* Existing normal text streaming and thinking streaming behavior must continue to work.
* The fix must be narrowly scoped to the Responses/OpenAI compatibility layer and avoid changing unrelated gateway replay contracts.

## Acceptance Criteria

* [ ] A non-streaming `/v1/responses` response with text `Tool call requested: Shell {...}` and a matching requested tool emits an output item of type `function_call` with name `Shell` and JSON arguments.
* [ ] A streaming `/v1/responses` response with the same text shape emits a function-call output item and function-call arguments events, not assistant `output_text` events.
* [ ] Ordinary text responses still emit text output items/events.
* [ ] Existing unit tests for OpenAI compatibility pass, with focused tests added for the IDE tool-call fallback.
* [ ] Real WSL test requirement is considered and run if feasible for this API/gateway change.

## Out of Scope

* Replacing the current real-tested text-history replay of prior tool outputs with structured AI Studio `functionResponse` parts.
* Changing built-in frontend UI behavior.
* Changing account rotation or request-log storage behavior.

## Technical Notes

* Relevant spec: `.trellis/spec/backend/quality-guidelines.md`, scenario `Client-Compatible Chat/Responses/Messages Gateway`.
* Relevant code path: `handle_openai_responses`, `_responses_output_items`, and `_build_responses_streaming_response` in `src/aistudio_api/application/api_service.py`.
* Relevant tests: `tests/unit/test_openai_compatibility.py`.
