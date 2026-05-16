# explore response speed improvements

## Goal

Explore whether response latency can be reduced for chat/Gemini generation requests, then implement low-risk improvements when the bottleneck is clear.

## What I already know

* User asked: "探索下能否加快响应速度".
* The project is a local FastAPI proxy for AI Studio, with OpenAI-compatible and Gemini-native routes.
* Chat/Gemini generation routes delegate into application services and then browser/pure HTTP gateway replay.
* Streaming is supported for chat completions and Gemini streamGenerateContent, so first-chunk latency matters.
* Project workflow requires real WSL environment testing for code/API/account/browser/gateway changes.

## Assumptions (temporary)

* Focus first on request latency visible to API clients, especially time to first streamed chunk.
* Prefer low-risk optimizations that keep external API behavior unchanged.
* Avoid broad rewrites unless profiling shows a clear bottleneck.

## Open Questions

* No blocking user question yet; inspect the code and tests first.

## Requirements (evolving)

* Identify the main request path for OpenAI chat completions and Gemini generate/streamGenerateContent.
* Look for repeated synchronous work, avoidable browser/page setup, avoidable full buffering, or expensive conversions before responses can start.
* Implement a focused improvement if the code shows a safe opportunity.
* Preserve compatibility for existing request/response shapes.
* Add or update tests for the changed behavior.

## Acceptance Criteria (evolving)

* [x] Findings are persisted under this Trellis task.
* [x] Any implemented optimization has targeted automated test coverage.
* [x] Unit tests relevant to the changed path pass.
* [x] WSL real-environment smoke test passes when code/API/gateway behavior changes.

## Definition of Done (team quality bar)

* Tests added/updated where appropriate.
* Lint / typecheck / project checks green where available.
* Docs/spec notes updated if behavior or conventions change.
* Rollout/rollback considered if risky.

## Out of Scope (explicit)

* Replacing the AI Studio browser replay architecture wholesale.
* Changing public API contracts.
* Adding unrelated feature work.

## Technical Notes

* Initial files inspected: README.md, src/aistudio_api/api/routes_openai.py, src/aistudio_api/api/routes_gemini.py, src/aistudio_api/application/chat_service.py, src/aistudio_api/infrastructure/gateway/replay_v2.py.
* Implemented optimization: BrowserSession template capture now uses a temporary GenerateContent route to capture request metadata and abort the dummy request instead of waiting for the dummy response body.
* Automated validation: `python -m pytest tests/unit/test_gateway_session_readiness.py tests/unit/test_streaming_stability.py -q`; `python -m pytest -q`.
* WSL real validation: copied checkout to `/home/bamboo/aistudio-api-speed-test`, started server with `AISTUDIO_ACCOUNTS_DIR=/home/bamboo/aistudio-api/data/accounts`, verified `/health`, streaming `/v1/chat/completions`, and non-streaming `/v1/chat/completions` using real account credentials.
* Spec update gate: updated `.trellis/spec/backend/quality-guidelines.md` with the Gateway Template Capture Latency contract because the optimization changes browser/gateway infrastructure behavior.
