# fix: restore simple chat responses

## Goal

Restore basic text-only chat behavior so a minimal `/v1/chat/completions` request returns usable assistant content again instead of silently producing an unusable 200 response.

## What I Already Know

* The user reports that simple conversation no longer works.
* The provided server log shows `POST /v1/chat/completions` returning `200 OK` for `model=gemini-3.1-flash-lite`, `contents=1`, `images=0`, `stream=True`, `attempt=1`.
* Because the route returns 200, the likely failure is inside streaming capture/replay/parsing or downstream SSE emission rather than request validation.
* Recent upstream changes touched account selection, gateway session readiness, streaming stability, and API service behavior.

## Assumptions

* A minimal text-only chat request should work with browser replay mode for stream and non-stream paths.
* A 200 streaming response with no body content is a regression unless the upstream explicitly returns an error chunk.

## Requirements

* Preserve existing OpenAI-compatible `/v1/chat/completions` response shape.
* Restore content emission for minimal text-only streaming chat requests.
* Keep non-streaming chat behavior working because it consumes the same upstream event path.
* Surface upstream errors as compatible error chunks or HTTP errors rather than silent empty success.
* Avoid unrelated behavior changes to image generation, account rotation, or model capability validation.

## Acceptance Criteria

* [x] A text-only streaming chat request emits at least one OpenAI SSE content delta when the upstream replay contains text.
* [x] A text-only non-streaming chat request returns `choices[0].message.content` when the upstream replay contains text.
* [x] Existing streaming error handling remains SDK-compatible.
* [x] Focused unit tests cover the regression.
* [x] Relevant tests pass locally.
* [x] Because this touches API/gateway code, WSL real-environment verification is run or a concrete blocker is recorded.

## Verification

* `python -m pytest tests/unit/test_streaming_stability.py tests/unit/test_static_frontend_capabilities.py tests/unit/test_openai_compatibility.py tests/unit/test_api_responses.py tests/unit/test_gateway_replay_request_contract.py tests/unit/test_gateway_session_readiness.py tests/unit/test_stream_parser.py tests/unit/test_response_parser.py tests/unit/test_request_rewriter.py tests/unit/test_wire_codec_mapping.py -q` — 79 passed.
* WSL real environment: copied the workspace to `/home/bamboo/aistudio-api-chat-regression-test`, started the service on port 18180 with `AISTUDIO_ACCOUNTS_DIR=/home/bamboo/aistudio-api/data/accounts`, and verified `/v1/chat/completions` for `gemini-3.1-flash-lite`.
* WSL stream request returned an SSE content delta `pong`, a stop chunk, usage, and `data: [DONE]`.
* WSL non-stream request returned `choices[0].message.content == "pong"` with usage.

## Definition Of Done

* Tests added or updated for the regression.
* Lint/typecheck or focused test suite passes.
* WSL real-environment test result is recorded for code/API/gateway changes.
* Task files and code changes are committed together per the project workflow.

## Out Of Scope

* Adding new chat features.
* Changing account selection policy.
* Reworking browser login or capture architecture beyond the root cause needed for simple chat.

## Technical Notes

* Initial files of interest: `src/aistudio_api/application/api_service.py`, `src/aistudio_api/infrastructure/gateway/streaming.py`, `src/aistudio_api/infrastructure/gateway/stream_parser.py`, and `tests/unit/test_streaming_stability.py`.