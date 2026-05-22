# Quality Guidelines

> Code quality standards for backend development.

---

## Overview

<!--
Document your project's quality standards here.

Questions to answer:
- What patterns are forbidden?
- What linting rules do you enforce?
- What are your testing requirements?
- What code review standards apply?
-->

(To be filled by the team)

---

## Forbidden Patterns

<!-- Patterns that should never be used and why -->

(To be filled by the team)

---

## Required Patterns

<!-- Patterns that must always be used -->

(To be filled by the team)

## Scenario: OpenAI Local Studio API, Interface Modes, and Image Tool

### 1. Scope / Trigger

- Trigger: Code changes `src/aistudio_api/api/routes_local_studio.py`, `src/aistudio_api/infrastructure/local_studio.py`, `src/aistudio_api/api/app.py` request-log eligibility, `AISTUDIO_LOCAL_STUDIO_DIR`, or the static `#studio` OpenAI Local Studio workbench.
- Use this contract for server-side local conversation persistence, arbitrary compatible endpoint forwarding, selectable OpenAI Chat / OpenAI Responses / Gemini / Claude interface modes, attachment storage, request-log capture, and Responses-mode `gpt-image-2` image-tool behavior.

### 2. Signatures

- `AISTUDIO_LOCAL_STUDIO_DIR` defaults to `data/local-studio` and stores `conversations/*.json` plus `files/<yyyymmdd>/<asset-id>.<ext>`.
- `POST /api/local-studio/models` accepts `{"base_url": str, "api_key"?: str, "timeout"?: int, "interface_mode"?: "openai"|"responses"|"gemini"|"claude"}` and returns `{"object": "list", "data": list[model], "interface_mode": str}`.
- `GET/POST/PATCH/DELETE /api/local-studio/conversations` and `POST /api/local-studio/conversations/bulk-delete {"ids": string[]}` manage local JSON conversations.
- `GET /api/local-studio/assets/{asset_path:path}` serves generated/uploaded local assets after path containment validation.
- `POST /api/local-studio/chat` accepts connection settings, `interface_mode`, `model`, optional `conversation_id`, `message`, `files`, `options`, and optional `rerun_from`.
- Non-stream chat returns `{"conversation": ..., "request": ..., "elapsed_ms": int, "upstream_id"?: str, "interface_mode": str}`. Stream chat returns Server-Sent Events with `local_studio.delta` and final `local_studio.completed` events.
- Payload helpers: `normalize_interface_mode(...)`, `local_studio_models_path(mode)`, `local_studio_chat_path(mode, model, stream=False)`, `build_local_studio_chat_payload(...)`, `parse_local_studio_output(...)`, `parse_local_studio_stream_event(...)`, `build_responses_payload(...)`, `validate_gpt_image_2_size(value)`, and `parse_responses_output(payload)`.

### 3. Contracts

- `base_url` must point at the selected provider root: `/v1` for OpenAI Chat, Responses, and Claude-compatible routes; `/v1beta` or an equivalent Gemini root for Gemini routes. Route helpers append `/models`, `/chat/completions`, `/responses`, `/models/{model}:generateContent`, `/models/{model}:streamGenerateContent`, or `/messages` according to `interface_mode`.
- `interface_mode` defaults to `responses` when omitted and must be one of `openai`, `responses`, `gemini`, or `claude`. Store the selected mode on Local Studio conversations and summaries so restoring a conversation restores its protocol.
- API tokens are runtime-only request fields. They must not be persisted to conversation files, docs, tests, or task artifacts.
- Tokens must be a single header line. Reject newline-containing tokens before making any upstream request.
- `/models` must hide image-only and specialist non-chat ids from the conversation picker: `gpt-image-*`, audio, realtime, TTS, transcription, and embedding models. Gemini model ids may arrive as `models/{id}` and must be normalized to picker ids without the prefix.
- Model rows returned to the UI must include capability metadata or have default capabilities inferred for text, files, reasoning, streaming, tools, structured output, and Gemini safety controls.
- Chat payloads must be mode-specific: OpenAI Chat -> `/chat/completions` `messages`; Responses -> `/responses` `input`; Gemini -> `contents` plus optional `generationConfig`; Claude -> `/messages` `messages` and `max_tokens`.
- Stream mode must set the provider stream flag when supported and normalize provider SSE chunks to `local_studio.delta` events. The final event must include the saved conversation as `local_studio.completed`.
- Request logging must include `/api/local-studio/models` and `/api/local-studio/chat` client requests plus manually recorded upstream request/response phases. Client `api_key`, `apiKey`, and `token` body fields and upstream `Authorization` headers must be redacted.
- The `timeout` setting must be passed into every Local Studio upstream client, including model list, non-stream chat, and stream chat.
- The static UI must clear an accepted Local Studio draft immediately after send, restore it on non-rerun failure, and keep stream/non-stream, interface mode, reasoning, model, and image settings in `openai.localStudio.settings.v1`.
- The `gpt-image-2` image tool is Responses-mode only. When enabled, Local Studio must send the `image_generation` tool through `/responses` and must not fall back to `/images/generations`; HTTP/transport failures surface as upstream errors, and no-candidate completions remain image-less.
- Generated image bytes from `b64_json`, `b64`, `result`, or data URLs must be saved under `AISTUDIO_LOCAL_STUDIO_DIR/files` and returned with `/api/local-studio/assets/...` URLs.
- Uploaded attachments are accepted as data URLs, saved locally, stripped of heavy inline fields in persisted JSON, and rehydrated as Responses `input_image` or `input_file` blocks when sent upstream.
- Rerun truncates the conversation to the selected previous user turn before rebuilding the Responses payload.
- The static UI must keep its settings in `openai.localStudio.settings.v1`; this browser storage may hold the user's runtime token, but server-side storage must not.

### 4. Validation & Error Matrix

- Empty/non-HTTP `base_url` -> HTTP 400 `invalid_request_error`.
- Unknown `interface_mode` -> HTTP 400 `invalid_request_error` listing the allowed values.
- Multiline `api_key`/`token` -> HTTP 400 `API token must be a single line` without echoing the token value.
- Missing `model` -> HTTP 400 `model is required`.
- Missing `message` and no files for a non-rerun chat -> HTTP 400 `message or files are required`.
- Invalid conversation id/path traversal asset path -> HTTP 400; missing conversation/asset -> HTTP 404.
- Upstream 4xx -> mirror the 4xx status with `upstream_error`; upstream 5xx/524 -> HTTP 502 with the upstream status embedded in the message.
- Upstream timeout -> HTTP 504 and persist an assistant error message.
- `gpt-image-2` size not `auto` or `WIDTHxHEIGHT` -> HTTP 400 before upstream call.
- `gpt-image-2` edges not multiples of 16, longest edge `>=3840`, ratio `>3:1`, pixels `<655,360`, or pixels `>8,294,400` -> HTTP 400 before upstream call.

### 5. Good/Base/Bad Cases

- Good: Real compatible endpoint returns models including `gpt-image-2` and audio ids; Local Studio returns chat-capable ids only, includes capability badges, and defaults to a text/chat model for the selected interface mode.
- Good: User switches `interface_mode` from OpenAI Chat to Gemini; model loading calls the Gemini models route shape, chat calls `:generateContent`, token usage is normalized, and restoring the conversation restores Gemini mode.
- Good: Responses stream emits provider chunks; backend emits incremental `local_studio.delta`, frontend renders the assistant placeholder while streaming, and final persistence arrives via `local_studio.completed`.
- Good: Request logs enabled; a Local Studio chat group contains client request, upstream request, upstream response, and client response phases without API token leakage.
- Good: Responses image tool returns `image_generation_call.result`; the image is saved locally and rendered in the UI.
- Good: Responses image tool returns no image candidate; Local Studio saves the completed conversation without generated images and does not call `/images/generations`.
- Good: User enters custom `3824x2144`; local validation accepts it as near-4K under the `<3840` edge rule.
- Base: Text-only Responses chat stores assistant text and usage without calling an image-generation endpoint.
- Bad: A key file containing both base URL and token is passed as a single Authorization header value.
- Bad: The UI advertises `3840x2160`, which violates the strict max-edge rule.

### 6. Tests Required

- Unit: model filtering excludes `gpt-image-*` and specialist non-chat ids for each interface mode and normalizes Gemini `models/{id}` names.
- Unit: interface-mode payload routing, upstream paths, response parsers, stream parsers, timeout propagation, and conversation `interface_mode` persistence for OpenAI Chat, Responses, Gemini, and Claude.
- Unit: conversation CRUD, bulk delete, asset path containment, and rerun truncation.
- Unit: Responses payload construction includes attachment blocks, reasoning, and image-generation tool options.
- Unit: `gpt-image-2` official size options and invalid custom sizes.
- Unit: chat persists assistant errors for upstream 524/timeouts and rejects multiline tokens without leaking secrets.
- Unit: Responses image-tool HTTP failures, transport failures, and no-candidate completions do not call `/images/generations`.
- Unit: request-log middleware records Local Studio client/upstream/client response phases and redacts client tokens plus upstream Authorization headers.
- Static: `#studio` route/sidebar, Local Studio interface selector, stream toggle, capability grid, immediate draft clearing, official size list, custom size, Responses-only image panel, and no `3840x2160` option.
- Static syntax: when editing `src/aistudio_api/static/app.js`, run `node --check src/aistudio_api/static/app.js`.
- Real: WSL API smoke with real account data must verify original Playground OpenAI Chat, Responses, Gemini, and Claude routes still return text/stream/usage as applicable.
- Real: WSL API smoke must verify Local Studio OpenAI Chat, Responses, Gemini, Claude, stream mode, timeout settings, request logs, and runtime-only compatible key credentials. If the key file stores `base_url` plus token on separate lines, pass them as separate request fields; never pass the whole file as one Authorization value.
- Real: Browser UI smoke must open `#chat`, send a Playground message, then open `#studio`, load models, send a streamed Local Studio message, verify the draft clears and token usage renders, and open `#requests` to confirm Local Studio request groups.
- Real image path: when image-tool code changes, WSL API smoke must reject `3840x2160`, generate a `1536x864` image, persist it, retrieve the local asset, and browser UI must verify the rendered image has non-zero natural dimensions.

### 7. Wrong vs Correct

#### Wrong

```python
key_file = Path("key.txt").read_text()
payload = {"base_url": "https://api.openai.com/v1", "api_key": key_file}
```

#### Correct

```python
base_url = str(payload.get("base_url") or "").strip()
token = str(payload.get("api_key") or "").strip()
if "\n" in token or "\r" in token:
	raise HTTPException(status_code=400, detail={"message": "API token must be a single line"})
```

#### Wrong

```python
response = await client.post(upstream_url(base_url, "/responses"), json=request_body)
```

#### Correct

```python
path = local_studio_chat_path(interface_mode, model, stream=stream)
request_body = build_local_studio_chat_payload(mode=interface_mode, model=model, messages=messages, options=options)
response = await client.post(upstream_url(base_url, path), json=request_body)
```

#### Wrong

```python
tool = {"type": "image_generation", "model": "gpt-image-2", "size": "3840x2160"}
```

#### Correct

```python
tool = {"type": "image_generation", "model": "gpt-image-2", "size": validate_gpt_image_2_size("3824x2144")}
```

#### Wrong

```python
response = await client.post(upstream_url(base_url, "/responses"), json=request_body)
response.raise_for_status()
```

#### Correct

```python
try:
	response = await client.post(upstream_url(base_url, "/responses"), json=request_body)
	response.raise_for_status()
except httpx.HTTPError:
	raise
```

## Scenario: Image Prompt Optimization With Reference Images

### 1. Scope / Trigger

- Trigger: Code changes `/v1/images/prompt-optimizations`, the image workspace prompt optimizer UI, image reference upload/selection, or multimodal chat request normalization.
- Use this contract whenever prompt optimization may need the same visual context as the eventual image generation/edit request.

### 2. Signatures

- `POST /v1/images/prompt-optimizations` accepts `{"prompt": str, "model": str, "style_template": str = "none", "thinking": str|bool = "off", "images"?: list[str|{"url": str}]}`.
- Frontend entry point: `optimizeImagePrompt()` sends `/v1/images/prompt-optimizations` from the image workspace.
- Frontend material conversion: `imageEditReferences` combines `imageBaseImage` and `imageReferences`; `imageRequestImages()` converts them to request-ready data URLs.
- Backend schema: `ImagePromptOptimizationRequest.images` uses the same compatible shape as `ImageRequest.images`.
- Temporary multimodal conversion helpers: `data_uri_to_file(..., tmp_dir=None)`, `url_to_file(..., tmp_dir=None)`, `normalize_chat_request(..., tmp_dir=None)`, and `normalize_gemini_request(..., tmp_dir=None)` default to `settings.tmp_dir`.

### 3. Contracts

- Text-only prompt optimization remains valid and must not include an `images` field when no image materials are selected.
- When image materials are selected, the WebUI must reuse `imageRequestImages()` before optimizing, not maintain a separate image conversion path.
- The backend optimizer request must include a text block with the optimization instructions and one `image_url` block per supplied image.
- The optimizer system/user instructions must explicitly tell the model to use supplied reference images so options do not drift away from the user's materials.
- Image-bearing optimization requests require a text-output, non-image-output model with `image_input=True`.
- `AISTUDIO_TMP_DIR` defaults to the platform system temp directory, not a hard-coded `/tmp`; helper functions must create the configured directory before writing temporary files.

### 4. Validation & Error Matrix

- Empty `prompt` -> HTTP 400 `prompt is required`.
- Unknown `style_template` -> HTTP 400 listing supported style templates.
- Image-output model used as optimizer -> HTTP 400 `must be a text prompt optimization model`.
- `images` supplied with a model that lacks image input -> HTTP 400 `does not support image input for prompt optimization` before any upstream client call.
- Invalid image entry -> HTTP 400 from shared image URL/data URI validation.
- Optimizer response without exactly three options -> HTTP 502 upstream error.

### 5. Good/Base/Bad Cases

- Good: User uploads a reference image, chooses `gemini-3-flash-preview`, clicks optimize, and the request body contains `images` plus a prompt tied to the reference image.
- Good: Request logs for a real UI/API call show `client_request.body_json.images` and an upstream request containing reference-image context.
- Base: User optimizes a text prompt without references; the API returns three JSON options as before.
- Bad: The WebUI sends only text to the optimizer while image generation later sends selected references.
- Bad: A Windows run tries to write multimodal temp files under `/tmp` and fails before the upstream call.

### 6. Tests Required

- Unit: `handle_image_prompt_optimization(...)` forwards supplied images into the optimizer chat contents and capture images.
- Unit: image-bearing optimization rejects a non-image-input optimizer model before calling the client.
- Unit: default multimodal temp-dir normalization accepts inline images on Windows and cleans created files.
- Unit/static: `optimizeImagePrompt()` builds a body, awaits `imageRequestImages()`, and sets `body.images` when images exist.
- Static syntax: when editing `src/aistudio_api/static/app.js`, run `node --check src/aistudio_api/static/app.js`.
- Real: WSL browser-backed API smoke must send `/v1/images/prompt-optimizations` with an image and verify a 200 response plus request-log `images` preservation.
- Real: WebUI smoke must upload/select a reference image, click optimize, and verify the network request includes `images` and returns three options.

### 7. Wrong vs Correct

#### Wrong

```javascript
await this.fetchJson('/v1/images/prompt-optimizations', {
	method: 'POST',
	body: JSON.stringify({ prompt, model: this.imagePromptOptimizerModel })
})
```

#### Correct

```javascript
const body = { prompt, model: this.imagePromptOptimizerModel }
const images = await this.imageRequestImages()
if (images.length) body.images = images
await this.fetchJson('/v1/images/prompt-optimizations', { method: 'POST', body: JSON.stringify(body) })
```

#### Wrong

```python
def normalize_chat_request(messages, requested_model, tmp_dir="/tmp"):
		...
```

#### Correct

```python
def normalize_chat_request(messages, requested_model, tmp_dir=None):
		tmp_dir = tmp_dir or settings.tmp_dir
		os.makedirs(tmp_dir, exist_ok=True)
		...
```

## Scenario: Dynamic Model List Refresh

### 1. Scope / Trigger

- Trigger: Code changes model capability metadata, `/v1/models`, `/v1beta/models`, browser-backed model discovery, or static UI model selectors.
- Use this contract whenever model availability can change independently of the static registry.

### 2. Signatures

- `GET /v1/models?refresh=<bool>` returns OpenAI-compatible `{"object": "list", "data": [...]}` metadata.
- `GET /v1beta/models?refresh=<bool>` returns Gemini-compatible `{"models": [...]}` metadata.
- `AIStudioClient.list_available_models() -> list[str]` returns browser-discovered model ids without the `models/` prefix.
- `BrowserSession.list_available_models() -> list[str]` opens/reads the AI Studio model picker and extracts model ids.
- `register_dynamic_models(models: Iterable[str]) -> list[ModelCapabilities]` registers discovered ids for strict validation.
- Frontend model refresh entry point: `refreshModels()` calls `loadModels(true)`.

### 3. Contracts

- Plain list calls (`refresh=false` or absent) must be fast and must not require an initialized browser client.
- Refresh calls attempt browser-backed model discovery when a runtime client is available; discovery failures log a warning and return the cached/static registry.
- Dynamically discovered text-like ids are registered with inferred generic text capabilities so strict validation paths can accept them.
- Static model metadata remains the fallback source of truth for known image models and models with special capabilities.
- Gemini list responses must be generated from the combined static plus dynamic model id set.
- Frontend refresh must preserve a selected model when it still exists; otherwise existing default-selection helpers choose a valid text/image/prompt-optimizer model.
- Frontend model loading must guard against stale responses when interface mode changes during refresh.

### 4. Validation & Error Matrix

- No runtime client + `/v1/models?refresh=true` -> HTTP 200 with cached/static model metadata.
- Browser discovery failure -> HTTP 200 with cached/static model metadata and a server warning.
- Duplicate discovered ids or `models/<id>` aliases -> one dynamic registry entry keyed by canonical id.
- Unknown dynamically discovered text model used in strict validation -> accepted after refresh with generic text capabilities.
- Unknown image-like dynamic model -> inferred as image-capable, but specialized image size support still depends on registry metadata.

### 5. Good/Base/Bad Cases

- Good: User clicks the WebUI refresh button, `/v1/models?refresh=true` runs, `gemini-3.5-flash` appears in the dropdown, and `gemini-3.5-flash:countTokens` passes strict model validation.
- Good: User switches from OpenAI-compatible mode to Gemini mode while a refresh is in flight; the stale OpenAI response does not overwrite the Gemini model list.
- Base: Server starts without browser mode or without a ready client; `/v1/models` still returns static metadata.
- Bad: The UI shows a dynamically discovered model, but the backend rejects it because only the frontend list was updated.
- Bad: Model list refresh fails the whole endpoint because AI Studio UI scraping changed.

### 6. Tests Required

- Unit: static registry includes newly known models and exposes expected capabilities.
- Unit: `register_dynamic_models(...)` makes a discovered text model available to `strict=True` lookup.
- Unit/API: `/v1/models?refresh=true` and `/v1beta/models?refresh=true` call the runtime model discovery hook and include registered dynamic models.
- Unit: browser session extraction normalizes `models/` prefixes, lowercases ids, and de-duplicates results.
- Unit/static: frontend exposes loading state, refresh buttons, `?refresh=true` model URL construction, and stale-response guards.
- Static syntax: when editing `src/aistudio_api/static/app.js`, run `node --check src/aistudio_api/static/app.js`.
- Real: WSL browser-backed smoke must call refreshed model APIs and use the refreshed model in at least one strict-validation API route.

### 7. Wrong vs Correct

#### Wrong

```python
@router.get("/v1/models")
async def list_models(client: AIStudioClient = Depends(get_client)):
	return {"object": "list", "data": await client.list_available_models()}
```

#### Correct

```python
@router.get("/v1/models")
async def list_models(refresh: bool = Query(False)):
	data = await refresh_model_metadata(runtime_state.client) if refresh else list_model_metadata()
	return {"object": "list", "data": data}
```

## Scenario: Correlated API and AI Studio Request Logging

### 1. Scope / Trigger

- Trigger: Code changes the request-log store, API exchange logging middleware, `/request-logs` APIs, static request-log UI, account client pooling, or AI Studio replay/streaming send boundaries.
- Use this contract whenever implementing or refactoring optional capture of the complete client-backend-AI Studio request flow.

### 2. Signatures

- `AISTUDIO_REQUEST_LOGS_DIR` sets the durable request-log root and defaults to `data/request-logs`.
- `RequestLogStore.status() -> {"enabled": bool, "count": int, "group_count": int}` where `count` is stored phase entries and `group_count` is complete request lifecycles.
- `RequestLogStore.set_enabled(enabled: bool) -> {"enabled": bool, "count": int, "group_count": int}`.
- `RequestLogStore.save(kind, model, method, url, headers, body, captured_headers=None, transport="", chain_id=None, direction="outbound", phase=None, status_code=None, response_headers=None, response_body=None, elapsed_ms=None) -> dict | None`.
- `RequestLogStore.attach_response(request_id, status_code=None, response_headers=None, response_body=None, elapsed_ms=None) -> dict`.
- `RequestLogStore.list_groups(limit=None) -> list[dict]`, `get_group(chain_id) -> dict`, `export_groups(chain_ids) -> {"data": list[dict], "missing": list[str]}`, `delete_group(chain_id) -> dict`, and `delete_groups(chain_ids) -> dict`.
- Request-log context helpers: `new_request_chain_id()`, `set_request_chain_id(chain_id)`, `reset_request_chain_id(token)`, `current_request_chain_id()`.
- `GET /request-logs/status`, `PUT /request-logs/status`, `GET /request-logs?limit=<int>`, `GET /request-logs/{request_id}`.
- Group management APIs: `GET /request-logs/groups/{chain_id}`, `DELETE /request-logs/groups/{chain_id}`, `POST /request-logs/groups/delete {"ids": string[]}`, and `POST /request-logs/export {"ids": string[]}`.
- Frontend route/hash: `#requests`.

### 3. Contracts

- Request logging defaults to disabled and must persist the switch in the same store as the entries.
- API exchange logging for `/v1*` and `/v1beta*` routes creates correlated `client_request` and `client_response` entries when logging is enabled.
- AI Studio replay/streaming creates correlated `upstream_request` and `upstream_response` records for the same external API request.
- All entries produced for one external request must share the same `chain_id`; gateway saves inherit the request-scoped chain id.
- The request-log list API returns complete request lifecycle groups by default. `total` is group count, `entry_total` is phase-entry count, and every group id is the `chain_id`.
- A legacy entry without a usable `chain_id` is treated as a one-entry lifecycle keyed by its own `id`.
- Group detail responses include the group summary plus `entries` sorted by semantic phase order (`client_request`, `upstream_request`, `upstream_response`, `client_response`) and then time/id.
- Export and delete operations use complete request group ids, not individual phase entry ids. Deleting a group removes every entry in that lifecycle and leaves unrelated groups intact.
- `phase` values are semantic and UI-visible: `client_request`, `upstream_request`, `upstream_response`, `client_response`.
- Outbound `upstream_request` entries still represent AI Studio wire requests after `modify_body`, not inbound OpenAI/Gemini/Claude-compatible payloads.
- Non-streaming replay, streaming replay, image generation replay, and account-pooled clients must share the same `RequestLogStore` instance at runtime.
- Saved details must include id, timestamps, kind, model, transport, method, URL, sanitized replay headers, original captured headers, raw body, parsed JSON body when parseable, parse error when not parseable, and body size.
- Entries that carry a response must include status code when known, response headers when available, raw response body, parsed response JSON when parseable, response parse error when not parseable, response body size, and elapsed milliseconds when known.
- `upstream_request` entries attach their AI Studio response via `attach_response(...)` and may also have a separate `upstream_response` phase entry for timeline readability.
- The feature intentionally does not redact stored outbound request details because the UI must not lose information.
- The frontend request-log page must render the switch, grouped lifecycle list, selection controls, selected structured group detail, chain id, phase labels, status, raw body, response body, complete JSON record, and group-level delete/export actions.

### 4. Validation & Error Matrix

- Switch disabled -> `save(...)` returns `None` and writes no entry file.
- Invalid `request_id` -> `GET /request-logs/{request_id}` returns HTTP 400.
- Missing valid `request_id` -> `GET /request-logs/{request_id}` returns HTTP 404.
- Empty group id in store helpers -> `ValueError`; missing group id in route handlers -> HTTP 404 when syntactically present but not found.
- Batch export/delete with duplicate ids -> de-duplicate in request order; missing ids are reported in `missing` instead of failing the whole operation.
- `limit < 1` -> normalize to 1; `limit > 1000` -> normalize to 1000.
- Request-log write failure at replay boundary -> log a warning and continue the upstream request path.
- Unparseable body -> preserve `body_raw`, set `body_json` to null, and store `body_parse_error`.
- Unparseable response body -> preserve `response_body_raw`, set `response_body_json` to null, and store `response_body_parse_error`.

### 5. Good/Base/Bad Cases

- Good: User enables logging, sends `/v1/responses`, then opens `#requests` and sees four correlated phases: user to backend, backend to AI Studio, AI Studio to backend, backend to user.
- Good: User selects one grouped request and deletes it; all four phase entries disappear while other request groups remain.
- Good: User exports selected request groups and receives complete lifecycle JSON with each group's ordered `entries`.
- Good: Selecting an `upstream_request` entry shows both the rewritten AI Studio request body and attached AI Studio response body.
- Good: Balanced account rotation uses an isolated client but writes to the same request-log directory and switch as the main runtime client.
- Base: Logging remains off after startup until explicitly enabled, and normal chat/image/streaming requests run without creating files.
- Bad: Logging before `modify_body` stores client-compatible input instead of the actual AI Studio request body.
- Bad: Client request/response entries use one id while replay entries use another, so the UI cannot reconstruct the flow by `chain_id`.
- Bad: A pooled account client creates a private `RequestLogStore`, so the UI switch appears on while rotated requests are not captured.
- Bad: The detail UI renders only prettified JSON and drops raw body/headers, losing information.

### 6. Tests Required

- Unit: store default-off behavior, persisted toggle, entry summary, full detail, raw body, parsed JSON body, and header preservation.
- Unit: store response attachment, response body parsing, status code, elapsed time, phase, direction, and chain id fields.
- Unit/API: `/request-logs/status`, `/request-logs`, and `/request-logs/{id}` manage status, listing, detail, and invalid ids.
- Unit/API: grouped list/detail/export/delete cover group counts, entry counts, phase ordering, missing ids, and removal of every entry in a selected lifecycle.
- Unit: non-streaming `RequestReplayService.replay` logs the actual outbound body, attaches upstream response fields, and writes an `upstream_response` phase.
- Unit: `StreamingGateway.stream_chat` logs the rewritten outbound body and final raw streaming response while enabled.
- Unit/API: API exchange middleware logs correlated `client_request`, `upstream_request`, and `client_response` entries for a real route call.
- Unit/static: frontend exposes the `requests` route, toggle/status calls, grouped list/detail loading, selection, delete/export controls, phase labels, raw request body, response body view, and complete JSON rendering.
- Static syntax: when editing `src/aistudio_api/static/app.js`, run `node --check src/aistudio_api/static/app.js`; Python/static string tests do not catch JavaScript parse errors such as invalid `??`/`||` mixing.
- Real: WSL browser-backed smoke must enable logging, send a real API request, read list/detail in the WebUI, assert body/header preservation, response body preservation, and all four phases.

### 7. Wrong vs Correct

#### Wrong

```python
store = RequestLogStore()
client = AIStudioClient()
pool = AccountClientPool(account_store)
```

#### Correct

```python
store = RequestLogStore()
client = AIStudioClient(request_log_store=store)
pool = AccountClientPool(account_store, request_log_store=store)
```

#### Wrong

```python
store.save(body=inbound_payload)
modified_body = modify_body(captured.body, contents, model=model)
```

#### Correct

```python
modified_body = modify_body(captured.body, contents, model=model)
store.save(body=modified_body, headers=captured.replay_headers, captured_headers=captured.headers)
```

## Scenario: Client-Compatible Chat/Responses/Messages Gateway

### 1. Scope / Trigger

- Trigger: Code changes OpenAI-compatible Chat Completions, OpenAI Responses, Anthropic Messages, Gemini-native conversion, tool normalization, or SSE event translation.
- Use this contract whenever a client-facing protocol payload is translated into the browser-backed AI Studio chat path.

### 2. Signatures

- `normalize_openai_tools_and_search(tools) -> tuple[list[list[Any]] | None, bool]`
- `normalize_openai_tools(tools) -> list[list[Any]] | None`
- `handle_openai_responses(payload: dict[str, Any], client, request: Request | None = None)`
- `handle_messages(payload: dict[str, Any], client, request: Request | None = None)`
- `handle_messages_count_tokens(payload: dict[str, Any]) -> dict[str, int]`
- `POST /v1/responses`
- `POST /v1/messages`
- `POST /v1/messages/count_tokens`

### 3. Contracts

- OpenAI-compatible search tools are recognized at the shared normalization boundary, not separately in each route. Supported types include `web_search`, `web_search_preview`, `web_search_preview_*`, `web_search_*`, `browser_search`, `google_search`, and `search`.
- Search tool requests must append the AI Studio `google_search` tool template while preserving valid function tools in the same request.
- Unknown non-function tools still fail validation; do not silently drop unsupported tool types.
- `/v1/chat/completions`, `/v1/responses`, and `/v1/messages` must share the same function-tool and search-tool normalization behavior.
- `/v1/responses` must forward `thinking` values through the shared chat request path: `off` disables thinking, while `low`/`medium`/`high` set AI Studio thinking config overrides and keep `enable_thinking=True`.
- `/v1/responses` input history must accept text-like content block types `text`, `input_text`, and `output_text`; `output_text` commonly appears when clients copy prior Responses assistant output back into the next request.
- `/v1/responses` input history must accept top-level Responses tool-continuation items emitted by prior turns: `function_call`, `function_call_output`, `tool_result`, and `input_tool_result`.
- Top-level Responses `function_call` history requires a non-empty string `name`; preserve `call_id -> name` while converting it to assistant text history shaped like `Tool call requested: <name> <arguments>`.
- Top-level Responses `function_call_output`/tool-result history must be converted to tool-result text history shaped like `Tool result for <name>: <output>` when the name can be recovered from the prior `call_id`, or `Tool result: <output>` otherwise.
- Top-level Responses `reasoning` history items are metadata and must be accepted and skipped rather than sent downstream or rejected with HTTP 400.
- Do not encode Responses follow-up tool results as structured AI Studio `functionResponse` wire parts unless a real browser-backed test proves the exact wire shape. The current real endpoint rejects the attempted structured `functionResponse` replay with `Unexpected list for single non-message field`; text history is the supported compatibility path here.
- When AI Studio returns a plain text response exactly shaped like `Tool call requested: <name> <json-arguments>` and `<name>` is one of the current Responses request's declared tools, `/v1/responses` must restore that text to a Responses `function_call` output item/event instead of exposing it as assistant text. This fallback is required because real browser-backed tool requests can come back as compatibility text even when the outbound AI Studio wire contains tool declarations.
- Responses streaming must emit `response.function_call_arguments.delta` and `response.function_call_arguments.done` for both structured upstream tool calls and restored text-shaped tool calls.
- Responses streaming `response.output_item.added` for `function_call` items must be an in-progress shell with `arguments: ""`; clients reconstruct arguments by appending `response.function_call_arguments.delta`, so pre-populating the added item with the complete argument payload duplicates it into `{"..."}{"..."}` in Cursor/Responses-style clients.
- `/v1/responses` non-streaming output must preserve returned thinking as a Responses `reasoning` output item and as a top-level `thinking` convenience field for the built-in UI.
- `/v1/responses` with `stream: true` must translate chat thinking deltas into Responses SSE events `response.reasoning.delta` and `response.reasoning.done`, and the final `response.completed` payload must include accumulated `thinking`.
- `/v1/responses` with `stream: true` must return SSE events including `response.created`, `response.in_progress`, text deltas, text done, output item done, function-call argument events when tools are requested, `response.completed`, and final `data: [DONE]`.
- `/v1/messages` with `stream: true` must return Anthropic-compatible SSE events including `message_start`, content block start/delta/stop, `message_delta`, `message_stop`, and final `data: [DONE]`.
- `/v1/messages/count_tokens` returns `{"input_tokens": <int>}` using the same message/system/tool coercion assumptions as `/v1/messages`.
- These compatibility endpoints are practical subsets. Do not claim hosted OpenAI/Anthropic parity for background tasks, remote hosted tools, or provider-specific beta fields unless tests cover them.

### 4. Validation & Error Matrix

- Tool type `function` with a valid function object -> emit an AI Studio function declaration.
- Recognized search tool type -> set search enabled and append Google Search template.
- Recognized search tool plus function tools -> include both Google Search and function declarations.
- Unknown tool type -> `ValueError`/HTTP 400 with a clear unsupported tool message.
- Responses `stream: true` -> translate existing Chat SSE into Responses SSE; upstream stream errors become `response.failed` before `[DONE]`.
- Responses `thinking: "high"` -> outbound AI Studio generation config includes thinking config `[1, null, null, 3]` and request flag `1`.
- Responses upstream thinking text -> client receives a reasoning output item/top-level thinking in non-streaming mode, or reasoning delta/done SSE events in streaming mode.
- Responses upstream text exactly `Tool call requested: <declared-tool-name> <json-arguments>` -> client receives a Responses `function_call` output item/non-text streaming function-call events; malformed JSON, missing declared tool name, or undeclared tool name remains ordinary text.
- Responses assistant history containing `content: [{"type":"output_text","text":"..."}]` -> normalize as ordinary text history, not a local HTTP 400.
- Responses history containing top-level `function_call`, optional `reasoning`, and matching `function_call_output` -> normalize to continuation history, not a local HTTP 400.
- Responses `function_call` item missing a non-empty `name` -> HTTP 400 with `function_call items require name`.
- Messages `stream: true` -> translate existing Chat SSE into Messages SSE; upstream stream errors become `error` before `[DONE]`.
- Empty or unsupported message content blocks -> preserve best-effort text while avoiding local crashes.

### 5. Good/Base/Bad Cases

- Good: CherryStudio sends `tools: [{"type":"web_search"}]` to `/v1/chat/completions`; the request uses Google Search and returns an OpenAI-compatible chat response.
- Good: Codex/Responses-style client sends `stream: true`; it receives Responses event names and a completed response containing accumulated output text.
- Good: A Responses client replays the previous assistant message with `output_text` content in the next `input`; the proxy sends it downstream as model text history.
- Good: A Responses client sends a prior `function_call`, a `reasoning` item, and a `function_call_output`; the proxy converts the tool call/result into text history and the model continues.
- Good: Cursor sends Responses `tools` and AI Studio streams `Tool call requested: Shell {"command":"..."}` as text; the proxy restores it to Responses function-call events so the IDE can execute the tool.
- Good: Claude-compatible client sends `stream: true` to `/v1/messages`; it receives Anthropic event names and token usage deltas when available.
- Base: A request with only function tools behaves as it did before search-tool support.
- Bad: `/v1/chat/completions` accepts `web_search`, but `/v1/responses` rejects the same tool because it has a separate validator.
- Bad: `/v1/responses` emits `output_text` in one response, then rejects the same `output_text` block when the client sends it back as assistant history.
- Bad: `/v1/responses` forwards attempted structured `functionResponse` wire based only on fake-client tests, then real AI Studio rejects the request body before continuation.
- Bad: `/v1/responses` forwards `Tool call requested: Shell {...}` to the client as assistant text, so an IDE displays the request instead of executing the tool.
- Bad: `/v1/responses` streams a `function_call` item whose `response.output_item.added.item.arguments` already contains the complete JSON, then sends the same JSON again in `response.function_call_arguments.delta`; clients that merge initial item state plus deltas execute with duplicated invalid JSON arguments.
- Bad: Streaming wrappers emit text deltas but never emit done/completed events, leaving clients waiting.

### 6. Tests Required

- Unit: Chat Completions accepts each supported search-tool alias and appends the Google Search template.
- Unit: function tools and search tools can coexist without dropping either tool family.
- Unit: unknown tool types still fail with a clear validation error.
- Unit: Responses non-streaming output includes `web_search_call` when search was requested.
- Unit: Responses accepts assistant history content blocks with `type: "output_text"` and normalizes them to ordinary text/model history.
- Unit: Responses accepts top-level `function_call`, `reasoning`, and `function_call_output` input history and normalizes tool call/result text in downstream contents.
- Unit: Responses restores text-shaped tool requests for declared tools to non-streaming `function_call` output items.
- Unit: Responses streaming restores text-shaped tool requests for declared tools to `response.function_call_arguments.delta`/`done` events and does not emit assistant text deltas for that request.
- Unit: Responses streaming reconstructs function-call arguments from `response.output_item.added` plus `response.function_call_arguments.delta` into exactly one valid JSON payload for both structured upstream tool calls and restored text-shaped tool calls.
- Unit: Responses streaming still emits ordinary text deltas incrementally when the text is not a possible declared-tool request.
- Unit: Responses `thinking: "high"` forwards thinking config and `thinking: "off"` disables thinking.
- Unit: Responses non-streaming output includes returned thinking as reasoning output and top-level `thinking`.
- Unit: Responses streaming includes `response.created`, text delta/done, `response.completed`, and `[DONE]`.
- Unit: Responses streaming includes `response.reasoning.delta`, `response.reasoning.done`, and final completed `thinking` when upstream emits thinking.
- Unit: Messages streaming includes `message_start`, text delta, `message_stop`, and `[DONE]`.
- Unit: `/v1/messages/count_tokens` returns `input_tokens` for system, messages, and tools payloads.
- Real: WSL browser-backed smoke must cover Chat search, Responses streaming, Messages streaming, and Messages count_tokens for API/gateway changes.
- Real: WSL browser-backed smoke must replay any captured Responses tool-follow-up payload before claiming structured compatibility; fake-client tests alone are insufficient for AI Studio wire-shape changes.

### 7. Wrong vs Correct

#### Wrong

```python
if tool.get("type") != "function":
	raise ValueError("Unsupported tool type")
```

#### Correct

```python
function_tools, uses_search = normalize_openai_tools_and_search(tools)
if uses_search:
	tool_blocks.append(TOOLS_TEMPLATES["google_search"])
```

#### Wrong

```python
if payload.get("stream"):
	raise ValueError("streaming is not supported")
```

#### Correct

```python
if payload.get("stream"):
	return _build_responses_streaming_response(payload, client, request)
```

## Scenario: Static Frontend Interface Mode Selection

### 1. Scope / Trigger

- Trigger: Code changes the built-in static frontend's model-list, chat, image-generation, prompt-optimization, or interface-mode request paths.
- Use this contract whenever the UI can choose between OpenAI-compatible Chat Completions, OpenAI Responses, Gemini-native, or Claude/Anthropic-compatible routes.

### 2. Signatures

- `interfaceModeOptions -> list[{id, label}]`
- `validInterfaceMode(value) -> string`
- `selectInterfaceMode(value) -> void`
- `modelListEndpoint() -> string`
- `normalizeModelList(data) -> list[dict]`
- `normalizeGeminiModel(item) -> dict`
- `ensureTextModelDefaults() -> void`
- `chatRequestBody() -> dict`
- `responsesRequestBody() -> dict`
- `responseOutputThinking(payload) -> string`
- `claudeRequestBody() -> dict`
- `geminiChatRequestBody() -> dict`
- `geminiChatEndpoint(stream=false) -> string`
- `geminiMessageFromPayload(payload) -> {content, thinking, usage}`
- `imageGenerationEndpoint() -> string`

### 3. Contracts

- OpenAI-compatible behavior must remain the default interface mode.
- The built-in WebUI must expose one user-facing interface-mode dropdown on Playground and image generation pages, with these options: OpenAI compatible, OpenAI Responses, Gemini, and Claude.
- The built-in WebUI must expose visible model-selection dropdowns in Playground and image generation. Interface mode chooses the protocol/route; model selectors choose the concrete text/image model within the current model list.
- Model-list selection may call `GET /v1/models` or `GET /v1beta/models`, but the UI's internal model shape must still include `id` and `capabilities` so controls do not guess from raw API payloads at render time.
- OpenAI compatible mode sends Playground chat to `/v1/chat/completions`.
- OpenAI Responses mode sends Playground chat to `/v1/responses` and translates Responses output back to the existing transcript shape.
- OpenAI Responses mode must translate Responses thinking back to the existing transcript shape: assistant `thinking` plus the collapsible thinking block.
- Gemini mode sends Playground chat to `/v1beta/models/{model}:generateContent` or `:streamGenerateContent` and translates Gemini output back to the existing transcript shape.
- Claude mode sends Playground chat to `/v1/messages` and translates Anthropic message output back to the existing transcript shape.
- Gemini chat selection must translate the current transcript into `contents`, optional `systemInstruction`, optional `tools`, and optional `generationConfig` before calling `/v1beta/models/{model}:generateContent` or `:streamGenerateContent`.
- Gemini responses must be translated back to the existing transcript shape: assistant `content`, optional `thinking`, and normalized usage tokens.
- Image generation remains routed through `/v1/images/generations`; the interface-mode selector must not point image generation at nonexistent provider-native image routes.
- Account, rotation, stats, generated image files, and image-session endpoints are project management endpoints and must not be switched by the interface-mode selector.

### 4. Validation & Error Matrix

- Invalid stored interface preference -> fall back to `openai` and keep loading the UI.
- Legacy `aistudio.apiSelection.v1` preferences -> migrate best-effort to the unified interface mode, then use `openai` if the legacy value is not a valid mode.
- Gemini model list lacks project-specific capabilities -> infer conservative capabilities from known model id patterns and `supportedGenerationMethods`.
- Selected model is missing after switching model-list API or restoring an old session -> clear the previous model and select the first available text/image-capable model as appropriate, while keeping the visible selector rendered with an empty-list message if no compatible model exists.
- Gemini chat stream event has `error` -> show the error on the assistant message and continue stream cleanup.
- Responses or Claude stream event has `error` -> show the error on the assistant message and continue stream cleanup.
- Image generation has no image-capable model in the current model list -> disable submission with a clear in-page hint and render the model picker with an empty-list message.

### 5. Good/Base/Bad Cases

- Good: User switches interface mode to Gemini; the frontend calls `/v1beta/models`, strips the `models/` prefix internally, and still shows capability-driven controls.
- Good: User switches interface mode to OpenAI Responses; Playground calls `/v1/responses` and parses `output_text` or output message content into the transcript.
- Good: User switches interface mode to Claude; Playground calls `/v1/messages` and parses text content blocks into the transcript.
- Good: User switches chat to Gemini with Stream enabled; the frontend calls `/v1beta/models/{model}:streamGenerateContent` and parses Gemini SSE chunks into the transcript.
- Base: User keeps defaults; existing `/v1/models`, `/v1/chat/completions`, and `/v1/images/generations` behavior is unchanged.
- Bad: Playground or image generation hides the model selector, leaving users unable to change models even though multiple compatible models exist.
- Bad: A selector label implies provider-native image generation, but clicking generate sends an incompatible or nonexistent provider-native image request.
- Bad: Gemini model list is displayed raw and the rest of the UI loses capability gating for files, search, thinking, or image models.

### 6. Tests Required

- Unit/static: frontend exposes one interface-mode selector with OpenAI compatible, OpenAI Responses, Gemini, and Claude options.
- Unit/static: frontend exposes Playground text-model, image-generation model, and prompt-optimizer model dropdowns with empty-list fallback text.
- Unit/static: frontend interface-mode selector has a non-empty default label in markup and Alpine-bound state.
- Unit/static: interface-mode selector persists in `localStorage` and defaults to OpenAI-compatible endpoints.
- Unit/static: legacy `aistudio.apiSelection.v1` fallback remains safe.
- Unit/static: Gemini model-list normalization and Gemini chat endpoint/body helpers are present.
- Unit/static: Responses and Claude request builders and completion handlers are present.
- Unit/static: image generation goes through an endpoint helper that currently returns `/v1/images/generations`.
- Real: WSL smoke should serve `/static/index.html`, `/static/app.js`, `/v1/models`, and `/v1beta/models` from a temporary WSL copy with real account data available.
- Real: WSL smoke should cover OpenAI compatible, OpenAI Responses, Gemini, Claude, and image generation request paths when this selector or its request builders change.

### 7. Wrong vs Correct

#### Wrong

```javascript
const r = await fetch('/v1/chat/completions', { method: 'POST', body: JSON.stringify(body) })
```

#### Correct

```javascript
if (this.interfaceMode === 'gemini') {
	return await this.completeGeminiChatFromCurrentMessages()
}
if (this.interfaceMode === 'responses') {
	return await this.completeResponsesChatFromCurrentMessages()
}
if (this.interfaceMode === 'claude') {
	return await this.completeClaudeChatFromCurrentMessages()
}
return await this.completeOpenAIChatFromCurrentMessages()
```

#### Wrong

```javascript
return data.models
```

#### Correct

```javascript
return data.models.map(item => this.normalizeGeminiModel(item)).filter(item => item.id)
```

## Scenario: Gateway Replay Uses Captured Request Contract

### 1. Scope / Trigger

- Trigger: Browser-backed capture/replay code crosses capture service, replay service, streaming gateway, and browser session boundaries.
- Use this contract whenever replaying an AI Studio `GenerateContent` request captured from the browser.

### 2. Signatures

- `CapturedRequest.url: str`
- `CapturedRequest.headers: dict[str, str]`
- `CapturedRequest.body: str`
- `CapturedRequest.replay_headers: dict[str, str]`
- `BrowserSession.send_hooked_request(*, body: str, url: str, headers: dict[str, str], timeout_ms: int)`
- `BrowserSession.send_streaming_request(*, body: str, url: str, headers: dict[str, str], timeout_ms: int)`

### 3. Contracts

- Capture is responsible for returning a complete `CapturedRequest` containing the replay URL, original headers, and template body.
- Capture must accept the current AI Studio RPC endpoint shape as well as older URL shapes. In real AI Studio sessions, text generation may be emitted to `https://alkalimakersuite-pa.clients6.google.com/$rpc/.../MakerSuiteService/GenerateContent`, not only to `aistudio.google.com` or `.../batchexecute/GenerateContent`.
- Template capture must only accept request bodies that parse as the AI Studio JSON array wire body. Skip empty, form-encoded, object-shaped, or otherwise non-JSON bodies even when the URL contains `GenerateContent`; `CapturedRequest.__post_init__`, snapshot rewriting, and wire-codec logic all require a parseable array template.
- Browser-session prompt filling must update the UI the same way a user does: focus/click the textarea, fill the text, and dispatch input/change events before clicking the enabled run control. Do not click `aria-disabled="true"` run buttons and treat that as success.
- Replay and streaming must pass `captured.url` and `captured.replay_headers` into `BrowserSession`; they must not ask the session to rediscover URL/header state from private template caches.
- `CapturedRequest.replay_headers` must exclude hop/body-length headers that browser XHR should not set manually: `host` and `content-length`.
- Pure HTTP replay may still use `captured.url` directly with an HTTP client and the same sanitized headers.

### 4. Validation & Error Matrix

- `captured is None` -> replay returns `(0, b"")` or streaming raises a clear captured-request error.
- Missing/invalid auth after replay reaches AI Studio -> propagate upstream authentication/authorization status.
- Empty session template cache with valid `CapturedRequest` -> replay must still send the browser XHR using captured URL/headers.
- Current `alkalimakersuite-pa.clients6.google.com/.../GenerateContent` template URL -> capture and replay it directly; do not filter it out because the host is not `aistudio.google.com`.
- `GenerateContent`-looking URL with an empty or non-JSON request body -> ignore it and keep waiting for the real JSON array template body; do not cache it as a template.
- Filled textarea but run button remains `aria-disabled="true"` -> report trigger failure instead of pretending a click succeeded.

### 5. Good/Base/Bad Cases

- Good: A cached snapshot returns `CapturedRequest`; replay uses `captured.url` and succeeds without reading `BrowserSession._templates`.
- Good: A fresh real WebUI/API send captures `alkalimakersuite-pa.clients6.google.com/$rpc/.../GenerateContent`, replays it through the browser, and writes a request-log entry when logging is enabled.
- Base: A fresh capture returns `CapturedRequest`; replay and streaming both use the same captured URL/header contract.
- Bad: Account switching clears `BrowserSession._templates`, capture reuses a service-level cached template, and replay fails locally with `no captured URL available for replay`.
- Bad: Template capture filters only `aistudio.google.com` URLs and times out even though the real page emitted a valid `GenerateContent` request to a Google RPC host.
- Bad: Template capture stores a `GenerateContent` request with a non-JSON body, and the next `/v1/responses` stream fails locally with `JSONDecodeError` while constructing `CapturedRequest`.

### 6. Tests Required

- Unit: non-streaming replay with a fake browser session that has no template cache; assert URL, sanitized headers, body, and timeout passed to `send_hooked_request`.
- Unit: streaming replay with a fake browser session that has no template cache; assert URL and sanitized headers passed to `send_streaming_request`.
- Unit: template capture accepts current `alkalimakersuite-pa.clients6.google.com/.../GenerateContent` RPC URLs, not only `aistudio.google.com` routes.
- Unit: template capture ignores `GenerateContent`-looking requests whose body is not a parseable JSON array.
- Unit: run-button clicking skips `aria-disabled="true"` controls and fills the prompt with input/change events.
- Integration/real: browser-backed `/v1/chat/completions` request returns an upstream result or upstream auth error, not local `no captured URL available for replay` or `template capture timeout`.
- Integration/real UI: built-in WebUI enables request logging through the UI, sends a Playground message successfully, opens `#requests`, and verifies the new entry detail contains `Body JSON`, `Body 原文`, and complete JSON.

### 7. Wrong vs Correct

#### Wrong

```python
return await self._session.send_hooked_request(body=body, timeout_ms=timeout * 1000)
```

#### Correct

```python
return await self._session.send_hooked_request(
	body=body,
	url=captured.url,
	headers=captured.replay_headers,
	timeout_ms=timeout * 1000,
)
```

##### Correct request-level image timeout override

```python
image_kwargs = {"prompt": prompt, "model": model}
if req.timeout is not None:
	image_kwargs["timeout"] = req.timeout
output = await client.generate_image(**image_kwargs)
```

```javascript
const timeout = this.normalizeImageTimeout()
const body = { model: this.imageModel, prompt, size: this.imageSize }
if (timeout) body.timeout = timeout
```

## Scenario: Browser Auth Changes Invalidate Capture State

### 1. Scope / Trigger

- Trigger: Code changes account activation, login completion, account rotation, browser auth switching, BotGuard snapshot retry, or request capture template caching.
- Use this contract whenever a browser-backed request may run after the active Google account or auth storage state changes.

### 2. Signatures

- `RequestCaptureService.clear_templates() -> None`
- `AIStudioClient.switch_auth(auth_file: str | None) -> None`
- `AIStudioClient.clear_capture_state() -> None`
- `AIStudioClient.clear_snapshot_cache() -> None`
- `AccountService.activate_account(account_id, browser_session, snapshot_cache, busy_lock=None, keep_snapshot_cache=False)` where `browser_session` should be the `AIStudioClient` when available, not only `AIStudioClient._session`.

### 3. Contracts

- Account activation must invalidate every cache that depends on the previous browser auth context: `BrowserSession` context/templates, `RequestCaptureService` per-model templates, and `SnapshotCache` prompt/model entries.
- `AIStudioClient.switch_auth` is the preferred auth-switch boundary because it can update the browser session and clear client-level capture state together.
- `AIStudioClient.clear_snapshot_cache` must clear capture templates as well as snapshots; a fresh snapshot with a stale captured template can still replay stale headers/body context.
- Streaming auth-error retry must call the client cache-clear boundary and then retry with `force_refresh_capture=True`.
- Replay must still use the `CapturedRequest` URL and sanitized headers after refresh; cache invalidation must not regress the captured request replay contract above.

### 4. Validation & Error Matrix

- Account switch succeeds -> next request for an already-used model re-captures its hook template before replay.
- Auth error during first streaming attempt -> clear capture state, force fresh capture, retry once.
- Retry still returns upstream `401`/`403` -> propagate the upstream auth/permission error; do not loop indefinitely.
- Missing account auth file -> activation returns no account and must not update the active account registry.
- Pure HTTP client has no browser templates -> clear snapshots and tolerate missing `clear_templates`.

### 5. Good/Base/Bad Cases

- Good: Web UI activates a different account; the next `gemini-3.1-flash-lite` request logs a fresh `Hook 模板已就绪` before replay.
- Base: Snapshot-only retry for the same auth context clears snapshots and templates, then captures fresh request state once.
- Bad: Account switching passes only `client._session` into `AccountService`, clearing browser templates but leaving `RequestCaptureService._templates` from the previous account.
- Bad: Streaming retry clears only `SnapshotCache`; the new snapshot is inserted into a stale template captured with old auth headers.

### 6. Tests Required

- Unit: `RequestCaptureService.clear_templates` causes the next same-model capture to call `capture_template` again.
- Unit: `AIStudioClient.switch_auth` clears service-level capture templates.
- Unit: account activation routes pass the runtime client into `AccountService.activate_account`.
- Unit: OpenAI and Gemini streaming auth-error retry clears capture state once and retries with `force_refresh_capture=True`.
- Integration/real: browser-backed `/v1/chat/completions` with the affected model returns SSE chunks and `[DONE]` using real account credentials.

### 7. Wrong vs Correct

#### Wrong

```python
result = await account_service.activate_account(
	next_account.id,
	client._session,
	runtime_state.snapshot_cache,
)
```

#### Correct

```python
result = await account_service.activate_account(
	next_account.id,
	client,
	runtime_state.snapshot_cache,
)
```

#### Wrong

```python
def clear_snapshot_cache(self) -> None:
	_snapshot_cache.clear()
```

#### Correct

```python
def clear_snapshot_cache(self) -> None:
	self.clear_capture_state()
```

## Scenario: Premium-Preferred Model Account Selection

### 1. Scope / Trigger

- Trigger: Code changes model capability metadata, account rotation, pre-request account selection, account tier detection, or text/image model routing.
- Use this contract whenever choosing which stored Google account should serve an AI Studio model request.

### 2. Signatures

- `AccountMeta.tier: str` with allowed values `free`, `pro`, `ultra`.
- `AccountMeta.is_premium -> bool` returns true for `pro` and `ultra`.
- `AccountRotator.model_prefers_premium(model: str | None) -> bool`.
- `AccountRotator.get_next_account(model: str | None = None, *, require_preferred: bool = False, exclude_account_id: str | None = None) -> AccountMeta | None`.
- `_ensure_account_for_model(model: str | None) -> None` runs before OpenAI/Gemini chat or image requests are sent upstream.

### 3. Contracts

- Premium-preferred models include registered `image_output` models and model IDs containing a standalone `pro` token, including IDs prefixed with `models/`.
- A standalone `pro` token is bounded by start/end, `-`, `_`, or `.`, so `gemini-3.1-pro-preview` and `gemini-pro-latest` match, while unrelated words containing `pro` should not.
- When the active account is non-premium and a healthy Pro/Ultra account exists, `_ensure_account_for_model` must switch to a Pro/Ultra account before capture/replay.
- When no Pro/Ultra account is available, preserve fallback behavior unless `require_preferred=True`: log the fallback and use an otherwise healthy account rather than failing locally.
- Account selection must use the same auth-switch boundary as manual activation, so browser session state, capture templates, and snapshot cache are invalidated together.

### 4. Validation & Error Matrix

- Registered image model + Pro/Ultra available -> select Pro/Ultra.
- Registered Pro text model + Pro/Ultra available -> select Pro/Ultra.
- `models/<pro-model>` prefixed ID -> same selection result as bare model ID.
- Premium-preferred model + no Pro/Ultra available + `require_preferred=False` -> warn and fall back to available healthy account.
- Premium-preferred model + no Pro/Ultra available + `require_preferred=True` -> return no account so caller can keep or report the current state.
- Non-premium text model -> use any healthy account according to the rotator mode.

### 5. Good/Base/Bad Cases

- Good: A newly activated Free account receives a `gemini-3.1-pro-preview` request while a Pro account is healthy; the request switches to the Pro account before capture and succeeds.
- Base: `gemini-3.1-flash-lite` stays on the active healthy Free account.
- Base: `gemini-3.1-flash-image-preview` continues to prefer Pro/Ultra accounts via image capability metadata.
- Bad: Only image models are premium-preferred; `gemini-3.1-pro-preview` stays on a Free account and upstream returns `[7,"The caller does not have permission"]`.

### 6. Tests Required

- Unit: `AccountRotator.model_prefers_premium` returns true for `gemini-3.1-pro-preview`, `models/gemini-3.1-pro-preview`, and `gemini-pro-latest`.
- Unit: Pro text model selection picks a Pro/Ultra account over a Free account.
- Unit/integration: OpenAI-compatible chat handling switches from a Free active account to an available Pro/Ultra account before calling the client for a Pro text model.
- Regression: Existing image model premium-selection tests still pass.
- Real: WSL browser-backed `/v1/chat/completions` for a premium-preferred model returns a successful upstream result and leaves the active account premium when a Pro/Ultra account is available.

### 7. Wrong vs Correct

#### Wrong

```python
def model_prefers_premium(self, model: str | None) -> bool:
	return get_model_capabilities(model, strict=True).image_output
```

#### Correct

```python
def model_prefers_premium(self, model: str | None) -> bool:
	capabilities = get_model_capabilities(model, strict=True)
	return capabilities.image_output or _model_name_prefers_premium(capabilities.id)
```

## Scenario: Account-Backed Runtime Statistics

### 1. Scope / Trigger

- Trigger: Code changes OpenAI, Gemini, image generation, streaming, prompt optimization, account rotation, account-client pooling, or runtime stats recording.
- Use this contract whenever an upstream request is served by a stored Google account selected for that request. In pooled/balanced mode, the selected account may differ from the registry's current active account.

### 2. Signatures

- `runtime_state.record(model: str, event: str, usage: dict | None = None, *, image_size: str | None = None, image_count: int = 1) -> None`
- `AccountRotator.record_success(account_id: str, *, image_size: str | None = None, image_count: int = 1) -> None`
- `AccountRotator.record_rate_limited(account_id: str) -> None`
- `AccountRotator.record_error(account_id: str) -> None`
- `_record_request_result(model, event, usage=None, *, account_id=None, image_size=None, image_count=1) -> None`
- `RequestAccountContext.account_id -> str | None`

### 3. Contracts

- Model-level runtime stats and selected-account stats must be recorded through the same request-result boundary when a request-bound account exists.
- In account-client-pool mode, success, error, and rate-limit events must use `RequestAccountContext.account_id`; they must not read the current active account at record time.
- Legacy/no-pool paths may fall back to the current active account for stats only after account selection/activation has completed.
- Success, error, and rate-limited events must update both model totals and account totals exactly once for each counted upstream request.
- Image generation success must pass `image_size` and the number of returned image items into both model and account stats.
- Transient retry attempts that clear stale capture state, such as first-attempt auth errors or empty image responses, must not be counted as permanent account errors unless the retry also fails.
- Web image generation and prompt optimization must refresh both `/stats` and `/rotation` after completion or failure so UI totals match backend state.

### 4. Validation & Error Matrix

- Request-bound account exists + request succeeds -> model `success` increments and the selected account `success` increments.
- Request-bound account exists + upstream 429 with no successful retry -> model `rate_limited` increments and the selected account `rate_limited` increments.
- Request-bound account exists + final upstream error -> model `errors` increments and the selected account `errors` increments.
- First auth/empty-image attempt clears capture state and retry succeeds -> only one success is counted, no account error is recorded.
- No selected or active account exists -> model stats may be recorded, account stats are skipped.

### 5. Good/Base/Bad Cases

- Good: Web image generation on account A then account B leaves `/stats.totals.requests == 2` and the sum of `/rotation.accounts[*].requests == 2`.
- Base: OpenAI or Gemini streaming success records the final usage and updates the active account once after the stream completes.
- Good: Balanced mode request on account A records success on account A even if another request or manual action changes the active account before response accounting.
- Bad: Streaming builders call only `runtime_state.record`, so model totals increase while account totals remain stale.
- Bad: Request accounting reads `account_service.get_active_account()` after an upstream request handled by a pooled client, so stats can land on the wrong account.
- Bad: A first-attempt stale capture `401` is counted as an account error even though a fresh-capture retry succeeds.

### 6. Tests Required

- Unit: non-streaming image success updates active-account requests, success, and image usage with the same image count as model stats.
- Unit: account-pool chat success records the selected account and does not switch the active account.
- Unit: OpenAI and Gemini streaming success update selected-account stats after completion.
- Unit: auth-error and empty-image retries clear capture state and do not count transient errors when the retry succeeds.
- Frontend/static: image generation and prompt optimization call a shared stats refresh that loads both `/stats` and `/rotation`.
- Real: WSL API and Web smokes activate two stored Pro accounts, generate images on both, and assert model totals equal account totals without printing secrets.

### 7. Wrong vs Correct

#### Wrong

```python
runtime_state.record(model, "success", output.usage)
```

#### Correct

```python
_record_request_result(model, "success", output.usage, account_id=account_context.account_id)
```

## Scenario: Balanced Account Pool Request Binding

### 1. Scope / Trigger

- Trigger: Code changes `round_robin` behavior, account rotation, account-client pooling, chat/image/Gemini request handling, streaming response builders, or 429 retry routing.
- Use this contract whenever a normal upstream request should be distributed across stored accounts without making the caller aware of backend account selection.

### 2. Signatures

- `RotationMode.ROUND_ROBIN == "round_robin"` remains the public config/API value and means balanced mode.
- `AccountRotator.acquire_account(model=None, *, require_preferred=False, exclude_account_id=None, affinity_key=None) -> AccountLease | None`.
- `AccountLease.account: AccountMeta` and `await AccountLease.release()`.
- `AccountStats.in_flight: int` is exposed through `/rotation.accounts[account_id].in_flight`.
- `AffinityBinding(account_id: str, created_at: float, expires_at: float)` stores bounded in-memory affinity.
- `DEFAULT_AFFINITY_TTL_SECONDS == 3600` unless overridden for tests.
- `/rotation.accounts[account_id].affinity_load: int` and `.bound_users: int` expose current non-expired logical user/session bindings.
- `/rotation.accounts[account_id].affinity_ttl_seconds: int` exposes the binding lifetime used by the running process.
- `AccountClientPool.get_client(account_id: str) -> AIStudioClient | None`.
- `ChatRequest.user: str | None` may be used as an OpenAI-compatible affinity hint.

### 3. Contracts

- Balanced `round_robin` must select per request using current in-flight count, historical request count, rate-limit count, and a round-robin tie breaker.
- A selected account lease must be held until the non-streaming request returns, or until the streaming generator finishes/cancels.
- Request handlers must use the pooled `AIStudioClient` associated with the selected account; they must not call global `activate_account()` for normal balanced routing.
- Each pooled client must have its own `SnapshotCache` and browser/capture/session state. Global active-account switching remains only for legacy/no-pool and manual activation flows.
- Lightweight affinity may keep a logical user/session on the same account when that account is not more than one in-flight request above the least-busy account.
- Affinity is intentionally temporary: a binding expires one hour after it is created and must not be refreshed indefinitely by repeated use.
- Expired affinity bindings must be pruned before selection and before `/rotation` stats are returned, so expired bindings do not count as account load.
- Account load is the count of non-expired affinity bindings assigned to an account; this is exposed as both `affinity_load` and the UI-friendly alias `bound_users`.
- For OpenAI-compatible chat, `ChatRequest.user` is the preferred affinity key. Without it, derive a bounded in-memory affinity key from normalized first user content.
- Account lease logs must include the selected request-bound account id, tier, mode, selection reason, in-flight count, affinity load, and affinity TTL. Do not log cookies, auth file contents, or prompt bodies beyond existing sanitized request logs.
- The admin UI must not use `激活/待命` as the serving-state label in balanced mode. Display pool scheduling state (`可调度`, `处理中`, `冷却中`, etc.) separately from a `默认账号` marker for the registry active account.
- On 429, update the failed selected account, then retry with `exclude_account_id` so the next attempt uses another eligible account when available.
- If stored accounts exist but no eligible account can be leased, do not silently use the global fallback client; return a service-unavailable style error or wait for the shortest cooldown when appropriate.
- Manual activation, login completion, credential import, account deletion, and force-next must invalidate affected pooled clients so stale auth/capture state is not reused.

### 4. Validation & Error Matrix

- Two concurrent leases + two healthy accounts -> selected account IDs differ and both `in_flight` values increment while leased.
- Same affinity key + account not overloaded -> selected account remains stable.
- Same affinity key after the one-hour binding TTL -> previous binding is ignored and the request participates in normal balanced selection again.
- `/rotation` after active bindings -> selected accounts report positive `affinity_load`/`bound_users` and `affinity_ttl_seconds == 3600`.
- Different `ChatRequest.user` values + two healthy accounts -> requests can distribute across accounts even with identical message content.
- Selected account 429 -> that account gets `rate_limited`, retry excludes it, and success can be recorded on another account.
- Pooled account auth changes -> next request creates a fresh pooled client for that account.
- All healthy accounts cooling down -> wait for shortest cooldown rather than sending through an unrelated global client.
- No stored accounts configured -> fallback client behavior remains available for legacy single-auth operation.

### 5. Good/Base/Bad Cases

- Good: Two real Pro accounts handle two OpenAI-compatible chat requests with different `user` values, and `/rotation` shows each account has one success and zero in-flight requests after completion.
- Good: The accounts table shows a healthy unused account as `可调度` with `0` bound users, not as a misleading standby serving state.
- Base: Exhaustion mode still keeps the active account until it becomes unavailable.
- Base: Premium-preferred model selection still filters eligible accounts to Pro/Ultra before balanced picking.
- Bad: A binding created for one logical user lasts forever and keeps the user pinned to one account even after the TTL window.
- Bad: Normal balanced routing calls `AccountService.activate_account()` before each request, racing global auth/capture state across concurrent users.
- Bad: A pooled request succeeds on account A but records stats on account B because the active account changed before accounting.
- Bad: The admin UI shows a request-serving pooled account as `待命`, implying it is not used.

### 6. Tests Required

- Unit: balanced concurrent leases distribute across two accounts and release `in_flight` counts.
- Unit: affinity keeps the same account when not overloaded.
- Unit: affinity load is exposed and expires after the TTL.
- Unit: account lease logs include selected account id and affinity load.
- Unit: different OpenAI `user` values distribute across pooled clients.
- Unit: pooled chat uses account-bound clients without switching the active account.
- Unit: 429 retry excludes the failed account and records stats on both the failed and successful accounts.
- Static/frontend: account table exposes pool status, default-account marker, and affinity load without `激活/待命` serving-state labels.
- Integration/real: WSL browser-backed `/v1/chat/completions` with two real accounts returns successful responses for two distinct user affinity keys and `/rotation` shows balanced account success counts.

### 7. Wrong vs Correct

#### Wrong

```python
await _ensure_account_for_model(model)
output = await client.generate_content(...)
_record_request_result(model, "success", output.usage)
```

#### Correct

```python
account_context = await _request_account_context(
	client,
	model,
	affinity_key=affinity_key,
	exclude_account_id=exclude_account_id,
)
output = await account_context.client.generate_content(...)
_record_request_result(model, "success", output.usage, account_id=account_context.account_id)
await account_context.release()
```

#### Wrong

```javascript
<span x-show="a.id===activeId">激活</span>
<span x-show="a.id!==activeId">待命</span>
```

#### Correct

```javascript
<span :class="poolStatusClass(a)" x-text="poolStatusLabel(a)"></span>
<div x-show="a.id===activeId">默认账号</div>
<strong x-text="accountLoad(a)"></strong>
```

## Scenario: Streaming Chat Success Requires Visible Output

### 1. Scope / Trigger

- Trigger: Code changes OpenAI-compatible streaming, Gemini streaming, stream parser/classifier, browser replay, frontend SSE consumption, or runtime stats for chat streams.
- Use this contract whenever converting AI Studio streaming replay events into downstream OpenAI/Gemini SSE responses.

### 2. Signatures

- `AIStudioClient.stream_generate_content(...) -> AsyncIterator[tuple[str, object | None]]`
- Stream event types: `"body"`, `"thinking"`, `"tool_calls"`, `"usage"`, `"done"`.
- `_build_streaming_response(...) -> StreamingResponse` for `/v1/chat/completions`.
- `_build_gemini_streaming_response(...) -> StreamingResponse` for `:streamGenerateContent`.
- `sse_error(message, error_type="upstream_error", code="upstream_error")` for OpenAI-compatible stream errors.
- Frontend stream consumer must handle top-level `{"error": ...}` SSE payloads in addition to `choices` and usage chunks.

### 3. Contracts

- A streaming response is successful only after at least one visible output event is emitted: `body`, `thinking`, or `tool_calls`.
- `usage` and `done` events alone are not visible assistant output and must not be recorded as success.
- If upstream finishes with HTTP 200 but no visible output, the backend must emit an SSE error chunk and `data: [DONE]`, and record the request as an error.
- OpenAI-compatible streams must preserve SDK-compatible error chunks with `error.message`, `error.type`, `error.param`, and `error.code`.
- Gemini-compatible streams must emit a Gemini-style `error` payload with code/status/message.
- The static frontend must surface top-level stream error chunks in the assistant message; it must not silently ignore them because the HTTP status is 200.

### 4. Validation & Error Matrix

- `body` event with non-empty text -> emit content delta, record success after stream completion.
- `thinking` event with non-empty text -> emit thinking delta, record success after stream completion.
- `tool_calls` event with at least one call -> emit tool-call delta, finish as tool calls, record success after stream completion.
- `usage` only + stream end -> emit upstream error chunk, send `[DONE]`, record errors.
- Upstream raises `AuthError`, `RequestError`, `UsageLimitExceeded`, or another `AistudioError` -> emit compatible stream error and `[DONE]`, record errors unless a first-attempt retry succeeds.
- Frontend receives `data: {"error": ...}` -> set the current assistant message error from `error.message`.

### 5. Good/Base/Bad Cases

- Good: AI Studio returns `pong`; OpenAI stream emits a content delta, stop chunk, usage chunk, and `[DONE]`.
- Base: AI Studio returns a tool call only; OpenAI stream emits `delta.tool_calls` and finishes with `tool_calls`.
- Base: AI Studio returns reasoning text before visible body; stream emits thinking chunks and still counts as visible output.
- Bad: Parser classifies every upstream chunk as `unknown`; backend emits only an empty stop chunk and records success.
- Bad: Backend emits an SSE error chunk, but the Web UI ignores it because it only reads `choices[0].delta`.

### 6. Tests Required

- Unit: OpenAI stream with a fake upstream `body` event emits content and records success.
- Unit: OpenAI stream with only `usage` emits a top-level error chunk and `[DONE]`.
- Unit: Gemini stream with only `usage` emits a Gemini error payload and `[DONE]`.
- Static/frontend: stream parser code checks `d.error` before usage/choice handling and writes it into the assistant message.
- Real: WSL browser-backed `/v1/chat/completions` stream for a text-only prompt returns at least one content delta and `[DONE]` with real account credentials.

### 7. Wrong vs Correct

#### Wrong

```python
async for event_type, text in upstream:
    if event_type == "usage":
        final_usage = text

_record_request_result(model, "success", final_usage)
yield sse_chunk(chat_id, model, "", finish="stop")
yield "data: [DONE]\n\n"
```

#### Correct

```python
saw_content = False
async for event_type, text in upstream:
    if event_type == "body" and text:
        saw_content = True
        yield sse_chunk(chat_id, model, text)
    elif event_type == "thinking" and text:
        saw_content = True
        yield sse_chunk(chat_id, model, "", thinking=text)
    elif event_type == "tool_calls" and text:
        saw_content = True
        yield sse_chunk(chat_id, model, "", tool_calls=to_openai_tool_calls(text))
    elif event_type == "usage":
        final_usage = text if isinstance(text, dict) else None

if not saw_content:
    raise RequestError(502, "AI Studio returned no response content")

_record_request_result(model, "success", final_usage)
```

#### Correct Frontend Error Handling

```javascript
const d = JSON.parse(line.slice(6))
if (d.error) {
  this.msgs[idx].error = d.error.message || JSON.stringify(d.error)
  continue
}
```

## Scenario: Image Model Capture with Proxied AI Studio Sessions

### 1. Scope / Trigger

- Trigger: Code changes browser session launch, proxy configuration, AI Studio navigation, image model selection, image onboarding, capture template caching, or image generation retry behavior.
- Use this contract for browser-backed image models such as `gemini-3.1-flash-image-preview` and `gemini-3-pro-image-preview`.

### 2. Signatures

- `settings.proxy_server: str | None`
- `settings.camoufox_locale: str`
- `settings.camoufox_timezone: str`
- `settings.camoufox_geolocation_latitude: float`
- `settings.camoufox_geolocation_longitude: float`
- `settings.camoufox_geolocation_accuracy: int`
- `camoufox_proxy_identity_options() -> dict[str, object]`
- `BrowserSession._prepare_model_onboarding_sync(page, model: str) -> bool`
- `BrowserSession._capture_template_request_with_recovery_sync(page, model: str) -> dict[str, Any]`
- `AIStudioClient.clear_capture_state() -> None`

### 3. Contracts

- Proxied Camoufox sessions must include stable locale, timezone, and geolocation hints from `camoufox_proxy_identity_options()` instead of enabling runtime `geoip=True`.
- Runtime `geoip=True` is not allowed in project code because it can require `camoufox[geoip]` and download GeoLite data from GitHub during real WSL tests.
- Image model capture must open the AI Studio image-generation entry, complete required onboarding/terms prompts, and select the UI model card matching the requested image model before template capture.
- Navigation to `ai.google.dev/gemini-api/docs/available-regions` is a recoverable redirect during capture setup; retry AI Studio chat navigation before failing.
- If the page leaves the chat runtime during template capture, reopen AI Studio, reinstall hooks, and retry capture once.
- If image replay returns a 200-shaped response with no parsed image data, clear capture state and retry once before returning a permanent upstream error.

### 4. Validation & Error Matrix

- Proxy configured -> Camoufox launch options include proxy plus `locale`, `config.timezone`, and `config.geolocation:*` values.
- AI Studio redirects to Google AI Developers available-regions docs -> navigation retries a chat URL and reports diagnostics only after retry failure.
- Image model requested -> image onboarding and model selection run before BotGuard snapshot/template capture.
- Template capture fill detaches because the page navigated away -> capture recovery reopens chat runtime and retries once.
- Empty image output on first attempt -> clear capture state and retry once; retry success returns `200` and records one success.
- Empty image output after retry -> return upstream error and record one final error.

### 5. Good/Base/Bad Cases

- Good: Account A generates `gemini-3-pro-image-preview`, account B generates the same model, then account A generates `gemini-3.1-flash-image-preview`; all three requests succeed and stats totals stay aligned.
- Base: A docs redirect during warmup is logged as a warmup failure but the next image capture opens a fresh browser context and succeeds.
- Bad: Enabling `geoip=True` makes WSL tests fail before the app starts because Camoufox tries to install or download GeoIP assets at runtime.
- Bad: Reusing a stale image template after an account switch returns `401` or a no-image response even though both stored accounts are valid Pro accounts.

### 6. Tests Required

- Unit: browser options and launcher options include proxy identity hints when `settings.proxy_server` is set.
- Unit: AI Studio docs redirect is retried and final diagnostics include the last URL/title/body when recovery fails.
- Unit: image model capture prepares onboarding/model selection before BotGuard snapshot readiness is required.
- Unit: template capture retries when a fill operation redirects or detaches the chat input.
- Unit: image generation retries one empty image response after clearing capture state and does not count the transient failure.
- Real: WSL API smoke uses a temporary copy under `/home/bamboo`, real accounts from `/home/bamboo/aistudio-api/data/accounts`, and verifies A -> B -> A image generation without printing credential contents.

### 7. Wrong vs Correct

#### Wrong

```python
options = {"proxy": {"server": settings.proxy_server}, "geoip": True}
```

#### Correct

```python
options = {"proxy": {"server": settings.proxy_server}}
options.update(camoufox_proxy_identity_options())
```

## Scenario: Browser Login Persists Only Verified Accounts

### 1. Scope / Trigger

- Trigger: Code changes browser-based Google account login, login status polling, account persistence, or post-login activation.
- Use this contract whenever a headed login browser captures Playwright storage state and may create a new account record.

### 2. Signatures

- `LoginSession.status: LoginStatus`
- `LoginSession.account_id: str | None`
- `LoginSession.email: str | None`
- `LoginSession.error: str | None`
- `AccountStore.validate_storage_state(storage_state: Any) -> str | None`
- `AccountStore.save_account(..., activate: bool = True) -> AccountMeta`
- `AccountService.activate_account(account_id, browser_session, snapshot_cache, busy_lock=None, keep_snapshot_cache=False) -> AccountMeta | None`

### 3. Contracts

- Browser login must validate captured storage state before saving it. A non-empty, non-expired Google cookie alone is not enough to prove the user finished login.
- Browser login must also detect authenticated account identity, preferably an email from the current page, `myaccount.google.com`, or validated storage-state local storage.
- If identity cannot be verified, the login session becomes `failed`, gets a clear error message, and must not create an account directory, registry entry, or active account.
- Browser-login-created accounts should be saved with `activate=False`; the account becomes active only after `AccountService.activate_account` switches the runtime browser/client auth successfully.
- Credential import can remain storage-state based and should not inherit the stricter headed-login identity gate unless that behavior is explicitly changed.

### 4. Validation & Error Matrix

- Storage state is malformed or has no valid Google cookie -> login session `failed`, no save.
- Storage state has Google cookies but no verified account identity -> login session `failed`, no save.
- Identity is detected and storage state is valid -> save account with `activate=False`, then login-status polling activates it through the runtime client.
- Activation fails after save -> report login/status failure; do not mark the saved account active.
- Existing imported/legacy accounts without email -> do not rewrite or delete them in the browser-login path.

### 5. Good/Base/Bad Cases

- Good: Login redirects away from `accounts.google.com`, email is found, storage state validates, account is saved inactive, and status polling activates it.
- Base: Login redirects but page email is missing; storage state local storage contains an email, so the account can still be saved inactive.
- Bad: Anonymous Google cookies validate structurally, the worker saves `email=None`, marks the account active, and later gateway calls fail with upstream auth/permission errors.

### 6. Tests Required

- Unit: fake login browser returns Google cookies without identity; assert session is `failed`, `account_id is None`, and the store remains empty.
- Unit: fake login browser returns a detected email; assert session is `completed`, account email is saved, and the store has no active account until activation.
- Unit/API: completed login status still activates a saved account exactly once through the runtime client.
- Real: WSL temp-copy validation uses the real accounts directory without printing credential contents and exercises at least one browser-backed `/v1/chat/completions` request.

### 7. Wrong vs Correct

#### Wrong

```python
meta = account_store.save_account(
	name=account_name,
	email=detected_email,
	storage_state=storage_state,
)
```

#### Correct

```python
detected_email = await self._verify_login_identity(account_store, page, storage_state, detected_email)
if detected_email is None:
	session.status = LoginStatus.FAILED
	session.error = LOGIN_IDENTITY_ERROR
	return

meta = account_store.save_account(
	name=account_name,
	email=detected_email,
	storage_state=storage_state,
	activate=False,
)
```

---

## Testing Requirements

<!-- What level of testing is expected -->

(To be filled by the team)

---

## Code Review Checklist

<!-- What reviewers should check -->

(To be filled by the team)
