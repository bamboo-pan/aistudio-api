# Fix tool call follow-up handling

## Goal

Fix OpenAI Responses compatibility so a client can send prior `function_call` items and matching `function_call_output` results back in `input` without a local HTTP 400. The proxy should preserve enough tool-call history for AI Studio to continue after the tool executes.

## What I already know

* User reported tool calls execute, but there is no follow-up handling.
* The provided request-log export `C:\Users\bamboo\Downloads\aistudio-requests-1(1).json` contains one `POST /v1/responses` lifecycle with status 400.
* The response body is `unsupported input item type: function_call`.
* The failing payload includes Responses `input` history with a top-level item `type: function_call`, followed by a `function_call_output` result.
* The failing payload also includes a top-level `type: reasoning` item between the tool call and tool output.
* Current `_messages_from_responses_payload` accepts `function_call_output` but rejects `function_call`.
* Existing response-side code can emit Responses `function_call` output items, so clients may naturally send them back on the next turn.
* WSL real testing showed AI Studio rejects the attempted structured `functionResponse` wire shape with `Unexpected list for single non-message field`; the final fix uses text history at the Responses compatibility boundary.

## Requirements

* `/v1/responses` must accept top-level `input` items with `type: function_call`.
* Function call history must be converted into model-readable assistant text history.
* Existing `function_call_output` history must be converted into model-readable tool-result text history, using the prior `call_id` to label the tool name when available.
* Top-level Responses `reasoning` history items must be accepted and ignored as metadata.
* The fix must preserve existing text, image, file, search, thinking, and streaming behavior.
* Unsupported item types must still fail with a clear HTTP 400.

## Acceptance Criteria

* [x] Replaying the shape from `aistudio-requests-1(1).json` no longer returns local `unsupported input item type: function_call`.
* [x] Unit tests cover Responses input history containing `function_call`, `reasoning`, and `function_call_output`.
* [x] Tool-call history is represented as text continuation history instead of rejected structured `functionResponse` wire.
* [x] Relevant compatibility tests pass on Windows and WSL.
* [x] WSL real environment API and frontend UI smoke tests pass for the changed route.

## Out of Scope

* Full hosted OpenAI Responses parity beyond the practical history replay subset.
* Hosted/background tool execution by this proxy.
* Structured Gemini/AI Studio function-response wire replay for Responses history.
* Changing request-log storage semantics unless needed for verification.

## Technical Notes

* Main conversion target: `src/aistudio_api/application/api_service.py` `_messages_from_responses_payload`.
* Existing tests: `tests/unit/test_openai_compatibility.py`, `tests/unit/test_api_responses.py`, `tests/unit/test_gemini_request_normalization.py`.
* Real API verification used a temporary WSL copy and posted the exact exported failing payload to `/v1/responses`; the response completed with no local 400 and no upstream protobuf shape error.
