# Failing Request Log Analysis

Source: `C:\Users\bamboo\Downloads\aistudio-requests-1(1).json`

## Observed Lifecycle

* Export contains one grouped lifecycle.
* Inbound request: `POST http://127.0.0.1:8080/v1/responses`.
* Model: `gemini-3.1-flash-lite`.
* Status: 400.
* Response body: `{"error":{"message":"unsupported input item type: function_call","type":"invalid_request_error","param":null,"code":null}}`.
* No upstream AI Studio request was recorded, so the failure happens in local request normalization before gateway replay.

## Payload Shape

The inbound Responses `input` array includes normal user/message history, then a top-level item:

```json
{
  "id": "fc_...",
  "type": "function_call",
  "status": "completed",
  "call_id": "call_...",
  "name": "...",
  "arguments": "..."
}
```

The existing code accepts top-level `function_call_output`, `tool_result`, and `input_tool_result`, but not top-level `function_call`.

The same history also includes a top-level Responses `reasoning` item. That item is client-visible metadata and does not need to be replayed as AI Studio input history.

## Root Cause

`_messages_from_responses_payload` rejects top-level Responses `function_call` history items even though `_responses_output_items` emits the same item type when the model requests a tool. A client that executes the tool and sends both the prior function call and the tool output back to `/v1/responses` is therefore rejected before model continuation.

## Implementation Direction

* Convert top-level Responses `function_call` input items to assistant history text such as `Tool call requested: <name> <arguments>`.
* Convert top-level Responses `function_call_output` items to tool-result history text such as `Tool result for <name>: <output>`, preserving the `call_id` to `name` mapping when available.
* Accept and ignore top-level Responses `reasoning` items because they are not user/model content to replay.
* Keep unsupported item types failing locally with a clear HTTP 400.

## Real Wire Finding

An initial implementation tried to replay the history as structured AI Studio `functionCall` and `functionResponse` parts. Unit tests with fake clients passed, but WSL browser-backed real API tests failed upstream with:

```text
Invalid value (), Unexpected list for single non-message field.
```

Bisection showed the real endpoint tolerated the function-call-like history shape in isolation, but rejected the attempted structured `functionResponse` shape. The final implementation therefore keeps the compatibility fix at the `/v1/responses` input boundary and sends tool-call/result history as plain text continuation context.

## Verification

* Windows related unit tests: 65 passed.
* WSL related unit tests: 65 passed.
* WSL real API replay of `C:\Users\bamboo\Downloads\aistudio-requests-1(1).json`: HTTP 200 SSE, `response.completed`, no `unsupported input item type: function_call`, no `Unexpected list`, no error event.
* WSL real WebUI smoke: opened the built-in Playground, selected OpenAI Responses mode, selected `gemini-3.1-flash-lite`, sent a message, and received a normal assistant reply with token usage updated.
* After merging latest `origin/master`, Windows related unit tests: 66 passed.
* After merging latest `origin/master`, WSL related unit tests: 66 passed.
* After merging latest `origin/master`, WSL real API replay of the same exported payload: HTTP 200 SSE, `unsupported_count=0`, `unexpected_list_count=0`, `completed_count=2`, `failed_count=0`.
* After merging latest `origin/master`, WSL real WebUI smoke: fresh browser state, OpenAI Responses mode, UI sent `POST /v1/responses` with HTTP 200 and rendered assistant reply `ok` plus token usage.
