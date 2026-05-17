# Verification

## Unit Tests

Command:

```bash
python -m pytest tests/unit/test_streaming_stability.py tests/unit/test_static_frontend_capabilities.py tests/unit/test_openai_compatibility.py tests/unit/test_api_responses.py tests/unit/test_gateway_replay_request_contract.py tests/unit/test_gateway_session_readiness.py tests/unit/test_stream_parser.py tests/unit/test_response_parser.py tests/unit/test_request_rewriter.py tests/unit/test_wire_codec_mapping.py -q
```

Result: 79 passed.

## WSL Real Environment

Environment:

* Test copy: `/home/bamboo/aistudio-api-chat-regression-test`
* Real accounts: `/home/bamboo/aistudio-api/data/accounts`
* Server port: 18180
* Model: `gemini-3.1-flash-lite`

Stream request:

* Endpoint: `POST /v1/chat/completions`
* Payload included `stream: true`, one user message, and `thinking: "off"`.
* Result: returned SSE content delta `pong`, final `finish_reason: "stop"`, usage, and `data: [DONE]`.

Non-stream request:

* Endpoint: `POST /v1/chat/completions`
* Payload included one user message and `thinking: "off"`.
* Result: returned `choices[0].message.content == "pong"` and usage.