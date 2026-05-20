# Fix duplicated tool call arguments

## Goal

Fix a Responses API tool-call serialization bug where downstream clients receive function-call arguments as two adjacent JSON objects, causing tool execution to fail with argument decode errors.

## What I already know

* The user reported a strange run using the exported request log `C:\Users\bamboo\Downloads\aistudio-requests-1(1).json`.
* The exported log contains one `/v1/responses` chain for `gemini-3.5-flash` with inbound client request, upstream `GenerateContent`, and outbound client response phases.
* The conversation in the client request shows repeated tool-call failures like `decode Ls args failed: invalid character '{' after top-level value`.
* The failed arguments are shaped like `{"path":"..."}{"path":"..."}`: two complete JSON objects concatenated.
* Existing unit tests cover basic Responses tool-call mapping and restoration, but do not yet guard against duplicated argument emission in streaming Responses events.

## Requirements

* Identify the root cause in the `/v1/responses` tool-call path.
* Ensure function-call arguments are emitted exactly once per tool call in both non-streaming and streaming Responses compatibility outputs.
* Preserve valid OpenAI Responses event semantics expected by clients.
* Add focused regression coverage for the duplicated-arguments case.
* Avoid broad refactors unrelated to the tool-call bug.

## Acceptance Criteria

* [x] A unit test reproduces the duplicated JSON object argument issue before the fix.
* [x] The fixed response stream contains a single valid JSON object for each function-call argument payload.
* [x] Existing OpenAI compatibility and streaming stability tests pass.
* [x] Real WSL environment API/UI verification is performed because this touches API behavior.

## Out of Scope

* Changing model/tool selection behavior.
* Changing unrelated request log UI or account rotation logic.
* Reworking the whole Responses compatibility layer.

## Technical Notes

* Likely code paths include `src/aistudio_api/api/responses.py`, `src/aistudio_api/application/api_service.py`, and OpenAI compatibility tests under `tests/unit/`.
* The failure appears client-visible, so inspect both `response.function_call_arguments.delta/done` events and final output item serialization.
* Root cause: Responses streaming emitted complete function-call `arguments` in `response.output_item.added.item.arguments` and emitted the same complete payload again through `response.function_call_arguments.delta`; clients that merge the initial item plus argument deltas reconstructed `{"..."}{"..."}`.
* Real API evidence is captured in `real-api-response.sse`: `response.output_item.added.item.arguments` is now empty while delta/done/output_item.done carry one complete valid JSON argument object.
