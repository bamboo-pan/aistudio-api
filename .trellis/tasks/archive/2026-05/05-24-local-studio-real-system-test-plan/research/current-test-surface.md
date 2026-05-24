# Current Test Surface Research

## Architecture Surface

Local Studio is a high-level WebUI workbench, not a replacement for the base pages. The test plan must therefore cover both of these layers:

* Standalone base entry points: Playground (`#chat`), image generation (`#images`), request logs (`#requests`), and account management (`#accounts`).
* Local Studio orchestration: provider profiles, interface modes, model loading, stream/non-stream, search, image generation tool, cache, conversations, attachments, and request-log lifecycle.

The request log service is shared across base modules and Local Studio. Real system tests must enable it before the critical runs and assert full lifecycle groups rather than checking only final UI text.

## Frontend Paths Inspected

`src/aistudio_api/static/index.html` exposes the relevant user controls:

* Sidebar navigation for Playground, Local Studio, image generation, request logs, and accounts.
* Local Studio provider selector, provider create/delete, base URL/token fields for OpenAI-compatible providers, and provider type display.
* Local Studio interface selector for OpenAI Chat, OpenAI Responses, Gemini, and Claude.
* Runtime controls for stream, Web search, cache namespace, reasoning, and Responses-only image tool controls.
* Provider-aware image tool fields: image model, size, custom size, and OpenAI-only quality/background/format/compression fields.
* Conversation lifecycle controls: create, restore, rename, rerun, single delete, and bulk delete.

`src/aistudio_api/static/app.js` builds Local Studio request options with provider, interface, search, cache, image tool provider/model/size, and OpenAI image-specific parameters.

## Backend Paths Inspected

`src/aistudio_api/api/routes_local_studio.py` handles:

* `/api/local-studio/models` by resolving provider settings, calling the provider `/models` path, and returning chat/image model lists.
* `/api/local-studio/chat` by saving the user message, building the mode-specific payload, handling cache hit/miss, and returning either JSON or SSE.
* Streaming upstream calls through `httpx.AsyncClient.stream`, then recording upstream request/response and saving the final assistant message.

`src/aistudio_api/infrastructure/local_studio.py` handles:

* Provider normalization for `google-ai-studio` vs `openai`.
* Interface modes: `openai`, `responses`, `gemini`, and `claude`.
* Responses payload tools: `web_search_preview` and provider-aware `image_generation`.
* Image model filtering and generated image de-duplication.
* Local request-cache keys separated by provider type, provider id/name, token hash, mode, model, request body, and namespace.

`src/aistudio_api/api/app.py` redacts Local Studio API keys from request-log middleware captures. The test plan must assert the request-log artifacts do not expose raw tokens.

## User-Reported Bug Oracles

### Gemini Image Tool Failure

The exported request log shows this real user path:

* Browser posts to `/api/local-studio/chat`.
* Provider: Google AI Studio.
* Interface: OpenAI Responses.
* Model: `gemini-3.5-flash`.
* Stream: enabled.
* Search: enabled.
* Image tool: enabled with provider `google-ai-studio`, image model `gemini-3.1-flash-image-preview`, size `1024x1024`.
* History includes ordinary chat, a search/news answer, and then user prompt `做成图片`.
* Upstream `/v1/responses` returns an SSE `event: error` with `Please enable tool_config.include_server_side_tool_invocations to use Built-in tools with Function calling.`

Regression tests must assert that this path either completes with a generated image or shows a controlled product-level error that is saved and displayed, but must not silently lose tool details, duplicate one image, or expose the raw upstream failure as an unhandled server error.

### OpenAI-Compatible Search Stream Failure

The server log shows this real user path:

* Browser posts to `/api/local-studio/chat`.
* Provider: custom OpenAI-compatible.
* Interface: OpenAI Responses.
* Search: enabled.
* Stream: enabled.
* Upstream `/v1/responses` returns HTTP 400.
* The backend then attempts `exc.response.content` on an unread streaming response and raises `httpx.ResponseNotRead`, producing an ASGI exception group.

Regression tests must assert that upstream streaming 4xx responses are converted to one client-visible SSE error, saved in the Local Studio conversation, recorded in request logs, and do not crash the ASGI app.

## Credential and Artifact Boundaries

Real tests must use the credential paths from `AGENTS.md`:

* Google AI Studio account credentials from the WSL accounts directory.
* OpenAI-compatible API key from the Windows key file path, read through WSL as `/mnt/c/Users/bamboo/Documents/github/key.txt` when running inside WSL.

No secret values, copied account files, browser storage state, raw request-log exports with tokens, or generated image assets should be committed.

## Relevant Existing Tests

Current unit/static tests cover payload helpers and frontend contract strings, but not full user paths:

* `tests/unit/test_local_studio.py` verifies provider resolution, model filtering, cache key separation, payload tools, and local route behavior with fake clients.
* `tests/unit/test_static_frontend_capabilities.py` verifies the Local Studio UI exposes provider, interface, search, cache namespace, image tool controls, and request log controls.

The new plan should treat these as prerequisites, not substitutes for real WSL API and browser UI tests.
