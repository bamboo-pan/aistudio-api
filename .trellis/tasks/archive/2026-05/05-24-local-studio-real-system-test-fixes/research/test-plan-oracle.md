# Local Studio Real System Test Oracle

## Source

Authoritative plan: `LOCAL_STUDIO_WEB_REAL_SYSTEM_TEST_PLAN.md`.

## Environment Contract

* Run from a fresh WSL copy under `/home/bamboo/aistudio-api-system-test-<timestamp>/repo`.
* Use real Google AI Studio credentials from `/home/bamboo/aistudio-api/data/accounts`.
* Read the OpenAI-compatible key from `/mnt/c/Users/bamboo/Documents/github/key.txt` only inside the test process and never print it.
* Use isolated runtime directories for `AISTUDIO_LOCAL_STUDIO_DIR`, `AISTUDIO_REQUEST_LOGS_DIR`, `AISTUDIO_GENERATED_IMAGES_DIR`, and `AISTUDIO_IMAGE_SESSIONS_DIR`.
* Keep screenshots, request-log exports, generated images, and server logs in the WSL temp `artifacts/` directory only after checking for secrets.

## Required First-Pass Evidence

* API health/model checks: `/api/local-studio/health`, `/request-logs/status`, `/v1/models`, `/v1beta/models`.
* UI route checks: `#studio`, `#chat`, `#images`, `#requests`, `#accounts` with console/network capture.
* Request logging lifecycle: `client_request`, `upstream_request`, `upstream_response`, `client_response`.
* P0 bug paths: Google Responses image tool with search, OpenAI-compatible Responses search streaming 4xx, OpenAI-compatible search tool type, OpenAI-compatible Responses reasoning.
* Base-module independence checks after intentionally bad Local Studio provider configuration.

## Core Oracles

* Google AI Studio Responses search uses `web_search_preview`; OpenAI-compatible Responses search uses `web_search` and never `web_search_preview`.
* Tool toggles are optional capability flags. Ordinary chat must not force search, image generation, or extra upstream calls.
* Reasoning/tool/search/image details returned by upstream must survive in at least API response, final SSE completed event, UI/current conversation, persisted conversation JSON, refresh/rerun/cache-hit path, and request logs where applicable.
* Cache keys must isolate provider type/id/name, normalized base URL, token hash, interface, model, namespace, body, search/image tool, reasoning, and attachments. Stream flag may reuse equivalent content while preserving response protocol.
* Errors must be controlled and consistent across API/SSE, UI, conversation JSON, request logs, server stderr, and health checks.
* Request-log exports, screenshots, server logs, task artifacts, and repository files must not contain real tokens, Authorization headers, Google cookies, storage states, or raw large image payloads.

## Durable Task Notes

Record initial and final test summaries in this task directory or final response, but do not commit raw secret-bearing artifacts. Include request-log group ids and screenshot paths only when they are safe and local to the temp run.
