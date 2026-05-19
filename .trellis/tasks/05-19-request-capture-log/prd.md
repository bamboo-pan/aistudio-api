# Request Capture Log

## Goal

Add an optional request-saving feature so operators can turn on capture and inspect every complete outbound request sent to AI Studio from the proxy.

## Requirements

- Provide a persisted backend switch for request saving; the default state is off.
- When the switch is on, save every complete request that the server sends to AI Studio, including non-streaming text generation, streaming text generation, and image generation.
- Save the actual outbound AI Studio request after body rewriting, including method, URL, headers, raw body, parsed JSON body when parseable, model, request kind, timestamps, and body size.
- Ensure account-rotated requests use the same switch and storage as the main runtime client.
- Add a frontend page with the switch, request list, and selectable request details.
- Render request details in an easy-to-read structure while preserving all information, including raw headers/body values.

## Acceptance Criteria

- [x] The backend exposes APIs to read/update the capture switch, list saved requests, and fetch a full request detail by id.
- [x] Request logs are not written while the switch is off.
- [x] Request logs are written for replayed non-streaming and streaming AI Studio requests while the switch is on.
- [x] Saved request details include raw request body and parsed JSON body without redaction or lossy transformation.
- [x] The frontend has a navigable request log page with a working toggle, list refresh, request selection, structured details, and raw body view.
- [x] Unit tests cover backend persistence, replay logging, streaming logging, routes, and frontend integration markers.
- [x] Real WSL environment test passes because this touches code/API/frontend/gateway behavior.

## Verification

- `C:/Users/bamboo/Desktop/aistudio-api_u1/.venv/Scripts/python.exe -m pytest tests/unit/test_request_logs.py tests/unit/test_gateway_replay_request_contract.py tests/unit/test_static_frontend_capabilities.py` - 20 passed.
- `C:/Users/bamboo/Desktop/aistudio-api_u1/.venv/Scripts/python.exe -m pytest tests/unit` - 255 passed.
- `C:/Users/bamboo/Desktop/aistudio-api_u1/.venv/Scripts/python.exe -m compileall -q src tests` - passed.
- WSL Ubuntu-24.04 real smoke using temporary copy, real account credentials, and running server on port 18091 - `WSL_REQUEST_LOG_SMOKE_OK`.

## Definition of Done

- Tests added or updated for the new backend and frontend behavior.
- Relevant project quality checks pass.
- Real WSL test passes with a temporary home-directory copy using real credentials path as required by project instructions.
- Task files under this Trellis directory are committed with the implementation.

## Technical Approach

Implement a file-backed request log store under the infrastructure layer and attach it to the runtime state. Pass the shared store into `AIStudioClient`, `RequestReplayService`, `StreamingGateway`, and `AccountClientPool` so all outbound replay paths share one persisted switch and log destination. Add a focused FastAPI router under `/request-logs` for status, listing, and detail retrieval. Extend the static Alpine app with a new sidebar page and JSON-detail renderer.

## Decision (ADR-lite)

**Context**: The proxy can accept requests through multiple compatibility APIs, but the user wants requests sent to AI Studio, not the inbound compatibility payloads.

**Decision**: Capture at the final replay boundary after `modify_body`, and save both raw and parsed representations.

**Consequences**: The saved data is faithful to AI Studio wire requests and covers all frontends, but it may include sensitive headers/cookies because completeness is prioritized.

## Out of Scope

- Editing, replaying, deleting, or exporting captured requests.
- Automatic retention limits or redaction.
- Capturing inbound OpenAI/Gemini/Claude/Responses requests separately from outbound AI Studio requests.

## Research References

- [`research/request-flow.md`](research/request-flow.md) - current request send paths and recommended capture point.

## Technical Notes

- Relevant backend files: `src/aistudio_api/infrastructure/gateway/client.py`, `src/aistudio_api/infrastructure/gateway/replay.py`, `src/aistudio_api/infrastructure/gateway/streaming.py`, `src/aistudio_api/application/account_client_pool.py`, `src/aistudio_api/api/app.py`.
- Relevant frontend files: `src/aistudio_api/static/app.js`, `src/aistudio_api/static/index.html`, `src/aistudio_api/static/style.css`.
- The initial user request is treated as the approved MVP scope per the project workflow instruction to continue unless clarification is truly blocking.