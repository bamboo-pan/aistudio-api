# API Contracts

> Executable request/response contracts for backend-facing APIs.

---

## Scenario: Local Inline File Inputs

### 1. Scope / Trigger

- Trigger: Playground and OpenAI/Gemini-compatible chat requests support local file attachments.
- Applies to `/v1/models`, `/v1/chat/completions`, `/v1/responses`, `/v1/messages`, and Gemini `:generateContent` / `:countTokens` request normalization.
- This contract covers local inline file data only. Remote Gemini `fileData.fileUri`, server-side file persistence, multipart uploads, and proxy-side Google Drive/File API uploads are out of scope.

### 2. Signatures

- Model metadata response: `capabilities.file_input: bool` and `capabilities.file_input_mime_types: list[str]`.
- OpenAI chat content block: `{"type":"file","file":{"file_data":"data:<mime>;base64,<data>","filename":"<name>","mime_type":"<mime>"}}`.
- OpenAI Responses/Messages input item: `{"type":"input_file","file_data":"data:<mime>;base64,<data>","filename":"<name>","mime_type":"<mime>"}`.
- Gemini part: `{"inlineData":{"mimeType":"<mime>","data":"<base64>"}}`.

### 3. Contracts

- `file_input=false` means UI must disable local file attachment controls and backend must reject non-image file input.
- `file_input_mime_types` supports exact MIME strings and wildcard groups such as `image/*`, `audio/*`, and `video/*`.
- Images sent as OpenAI `image_url` blocks continue to use `image_input` validation, not generic `file_input` validation.
- Non-image files sent through OpenAI file blocks or Gemini `inlineData` use `file_input` plus MIME allowlist validation.
- Inline data must be base64 and must not exceed the shared inline byte limit in `chat_service.MAX_INLINE_IMAGE_BYTES` unless that limit is intentionally renamed/changed.
- Image-output chat shortcuts still accept text prompts only; attachments must be rejected before image generation.

### 4. Validation & Error Matrix

- Empty or invalid base64 data -> `400` bad request with a message mentioning base64 data.
- File input on a model with `file_input=false` -> `400` bad request mentioning file input.
- MIME type not covered by `file_input_mime_types` -> `400` bad request mentioning the rejected MIME type and supported types.
- `image_url` with a non-image data URI -> `400` bad request mentioning image MIME type.
- Gemini `fileData.fileUri` -> `400` bad request; use `inlineData` for local uploads.
- Attachments on image-output chat shortcut -> `400` bad request; chat completions image generation supports text prompts only.

### 5. Good/Base/Bad Cases

- Good: `gemini-3-flash-preview` with `text/plain` file data reaches `AIStudioClient.generate_content` as `AistudioPart.inline_data=("text/plain", "...")`.
- Base: `gemini-3-flash-preview` image data sent as `image_url` remains accepted through the existing image input path.
- Bad: `gemma-4-31b-it` with `application/pdf` file data is rejected before downstream client calls.

### 6. Tests Required

- Model metadata tests assert `file_input` and representative MIME allowlist values.
- Chat capability tests reject file input for unsupported models and unsupported MIME types.
- OpenAI chat handler tests assert non-image file blocks are forwarded as `inline_data` and rejected for unsupported models.
- Gemini normalization tests assert non-image `inlineData` is accepted for file-capable models and rejected for non-file-capable models.
- Static frontend tests assert Playground uses `file_input`, `file_input_mime_types`, `chatFileAccept`, and generic file payload blocks.

### 7. Wrong vs Correct

#### Wrong

```json
{"type":"image_url","image_url":{"url":"data:application/pdf;base64,..."}}
```

This abuses the image path and should be rejected because `image_url` must carry images.

#### Correct

```json
{"type":"file","file":{"file_data":"data:application/pdf;base64,...","filename":"doc.pdf","mime_type":"application/pdf"}}
```

This uses generic file input validation and maps to AI Studio inline data.

---

## Scenario: Backend-Persistent Image Session History

### 1. Scope / Trigger

- Trigger: the static image generation page needs server-backed conversation history that survives browser reloads and can be restored for continued image editing.
- Applies to UI-only session history APIs under `/image-sessions` and lightweight JSON storage under the server runtime data directory.
- This contract is separate from `/v1/images/generations` and does not change OpenAI-compatible image generation request or response shapes.

### 2. Signatures

- Environment key: `AISTUDIO_IMAGE_SESSIONS_DIR` optionally overrides the image session JSON storage directory.
- Default storage: `DEFAULT_RUNTIME_DATA_DIR / "image-sessions"`.
- `GET /image-sessions` -> `{"data": list[ImageSessionSummary]}`.
- `POST /image-sessions` with an image session object -> full saved image session object.
- `GET /image-sessions/{session_id}` -> full saved image session object.
- `PUT /image-sessions/{session_id}` with an image session object -> full saved image session object.
- `DELETE /image-sessions/{session_id}` -> `{"ok": true, "id": "<session_id>"}`.
- Session IDs must match `^[A-Za-z0-9_-]{1,80}$`.

### 3. Contracts

- Session storage is backend-persistent JSON; it must not rely on browser `localStorage` for conversation recovery.
- Session payloads are lightweight snapshots: prompt, model, size, count, response format, current results, base image, references, conversation turns, and last request when available.
- Persisted image items must not store heavy inline image fields such as `b64` or `b64_json`; use generated image URLs/paths instead.
- Deleting a session deletes only the session JSON record. It must not delete generated image files or the local material library.
- Session summaries must include `id`, `title`, `created_at`, `updated_at`, `model`, `size`, `count`, `turn_count`, and `preview_url` when derivable.
- Listing returns newest sessions first and may prune old sessions according to the store's configured max count.

### 4. Validation & Error Matrix

- Non-object create/update payload -> `400 bad_request` with a message mentioning the session payload must be an object.
- Invalid `session_id` -> `400 bad_request` with a message mentioning invalid image session id.
- Missing session on read/delete -> `404 not_found` with `image session not found`.
- Corrupt session JSON files are ignored during list, not surfaced to the UI as a fatal list failure.

### 5. Good/Base/Bad Cases

- Good: UI saves a session with generated image URLs and later restores prompt, current results, base image/references, conversation, model, size, and count.
- Base: UI creates a fresh session with no `id`; backend generates the ID and returns the full saved record.
- Bad: UI sends `results[].b64_json`; backend strips it before writing JSON so the session store cannot grow with large inline payloads.

### 6. Tests Required

- Unit test that the store persists a lightweight snapshot, derives title/turn count/preview URL, and strips `b64_json`.
- Route round-trip test for create, list, get, and delete using a temporary `settings.image_sessions_dir`.
- Static frontend test that the image page calls `/image-sessions`, displays session history controls, restores sessions, deletes sessions, and clears the prompt after successful generation.
- Regression coverage that `/v1/images/generations` remains unchanged.

### 7. Wrong vs Correct

#### Wrong

```json
{"results":[{"url":"/generated-images/a.png","b64_json":"<large base64>"}]}
```

This stores large inline image payloads in conversation history and duplicates generated image files.

#### Correct

```json
{"results":[{"url":"/generated-images/a.png","path":"20260514/a.png"}]}
```

This keeps session history lightweight and relies on generated image persistence for the actual image bytes.

---

## Scenario: Account Rotation and Image Usage Stats

### 1. Scope / Trigger

- Trigger: account-management APIs expose rotation modes, per-account runtime stats, model totals, and tier-aware account checks.
- Applies to `/rotation`, `/rotation/mode`, `/rotation/next`, `/rotation/accounts`, `/stats`, and `POST /accounts/{account_id}/test`.
- This contract covers runtime in-memory stats only. Persistent analytics, quota reset windows, and long-term usage storage are out of scope.

### 2. Signatures

- Rotation mode request: `POST /rotation/mode` with `{"mode": "round_robin" | "lru" | "least_rl" | "exhaustion", "cooldown_seconds": int | null}`.
- Rotation status response: `{"enabled": bool, "mode": str, "cooldown_seconds": int, "accounts": dict[str, AccountRotationStats]}` when enabled.
- Account stats fields: `requests`, `success`, `rate_limited`, `errors`, `last_used`, `last_rate_limited`, `is_available`, `cooldown_remaining`, `image_sizes: dict[str, int]`, and `image_total: int`.
- Model stats response: `/stats` returns `{"models": dict[str, ModelStats], "totals": Totals}` where `totals.image_sizes` aggregates image counts by requested resolution and `totals.image_total` is their sum.
- Account check response: `POST /accounts/{account_id}/test` returns sanitized account health fields and may update `tier` when browser-based Pro/Ultra detection succeeds.

### 3. Contracts

- `exhaustion` mode keeps using the current active healthy account for automatic selection until it is rate-limited, isolated, expired, missing auth, unavailable, or unsuitable for the requested model tier preference.
- `/rotation/next` is a manual override and must exclude the current active account when another available account exists, even in `exhaustion` mode.
- `image_sizes` counts generated image items, not API requests. A successful request for `n=2` at `1024x1024` increments that resolution by 2.
- Image usage counters are added only after successful image generation. Validation failures, upstream errors, and rate limits must not increment image usage.
- Stats are backward-compatible: existing counters remain present and new `image_sizes` / `image_total` fields are additive.
- Account management is the UI home for runtime operations data: it must expose account/rotation stats and model-level `/stats` visibility rather than splitting model stats into a separate dashboard page.
- Account tier checks must not return credential payloads, cookies, raw storage state, or raw page header diagnostics in API responses.

### 4. Validation & Error Matrix

- Unknown rotation mode -> `400` with a message listing `round_robin`, `lru`, `least_rl`, and `exhaustion`.
- Rotator not initialized -> `503` for mutation/force-next endpoints.
- No available account for `/rotation/next` -> `404`.
- Account check for missing account -> `404`.
- Tier detector unavailable or failing after local credential health succeeds -> response remains `ok=true`, health stays `healthy`, and `health_reason` mentions tier detection unavailability.
- Local credential health failure -> response reflects `missing_auth`, `expired`, or `error`; tier detection is skipped.

### 5. Good/Base/Bad Cases

- Good: `mode=exhaustion` with a healthy active account returns that account for repeated automatic selections until `record_rate_limited(active_id)` marks it cooling down.
- Good: successful image generation with `size="1024x1024"` and one returned item increments model totals and active account stats under `image_sizes["1024x1024"]`.
- Base: existing `round_robin`, `lru`, and `least_rl` modes keep their previous selection behavior and response fields.
- Bad: force-next in `exhaustion` mode returning the current active account when another healthy account exists.
- Bad: account health/tier test response containing cookies, storage-state JSON, or raw detector headers.

### 6. Tests Required

- Unit tests for `exhaustion` keeping the active account and switching after rate limit.
- Unit test that force-next selection can exclude the active account.
- Unit tests for account and model `image_sizes` / `image_total` aggregation.
- Unit test that tier-aware account check can update a Free account to Pro/Ultra without leaking credentials.
- Static frontend tests that account management exposes `exhaustion`, resolution usage UI, model-level `/stats` totals/table, and no standalone dashboard navigation entry.
- WSL smoke test against the real accounts directory to verify account registry loading and stats shape.

### 7. Wrong vs Correct

#### Wrong

```python
rotator.record_success(account_id)
runtime_state.record(model, "success", usage)
```

For image generation this records only request success and loses requested resolution usage.

#### Correct

```python
rotator.record_success(account_id, image_size=image_plan.size, image_count=len(items))
runtime_state.record(model, "success", usage, image_size=image_plan.size, image_count=len(items))
```

The success counters remain backward-compatible while resolution-level image usage is available to `/stats`, `/rotation`, and the account-management UI.

---

## Scenario: Playground Local Chat Sessions and Usage Telemetry

### 1. Scope / Trigger

- Trigger: the static Playground chat page needs browser-local conversation recovery and visible token/cache telemetry for OpenAI-compatible chat responses.
- Applies to `src/aistudio_api/static/app.js`, `src/aistudio_api/static/index.html`, `src/aistudio_api/static/style.css`, `/v1/chat/completions` response helpers, and static frontend tests.
- This contract is additive for API clients: existing OpenAI usage fields remain present, and cache-related fields are added when normalized usage is emitted.

### 2. Signatures

- Browser storage key: `aistudio.chatSessions.v1`.
- Storage shape: `{"activeId": str, "sessions": list[ChatSession]}`.
- `ChatSession` fields: `id`, `title`, `createdAt`, `updatedAt`, `model`, `chatPreset`, `cfg`, and lightweight `msgs`.
- Normalized OpenAI usage fields: `prompt_tokens`, `completion_tokens`, `total_tokens`, `cached_tokens`, `prompt_tokens_details.cached_tokens`, and `completion_tokens_details.reasoning_tokens`.
- Gemini usage metadata includes `cachedContentTokenCount` derived from the same cache-token source.

### 3. Contracts

- Chat sessions are localStorage-only and per browser profile; they must not require a backend chat-session API.
- Session snapshots store enough state to restore conversation text, assistant thinking, usage, selected model, preset, and chat settings.
- Session snapshots should remain lightweight. Uploaded file data URLs must not be persisted indefinitely; restored file messages may keep text and lightweight metadata only.
- The Playground must remove the topbar Chat Settings dropdown when settings are already exposed inline in the workbench.
- Streaming chat must attach the final `choices: []` SSE usage chunk to the current assistant message.
- Non-streaming chat must attach the JSON response `usage` object to the assistant message.
- Cache telemetry must be displayed only when present or as zero/"miss" values; missing cache fields must normalize to `0` instead of breaking UI rendering.

### 4. Validation & Error Matrix

- Invalid or missing localStorage payload -> create a fresh local chat session and show a local history error only when storage access itself fails.
- localStorage quota/security error on save -> keep the in-memory session usable and surface a save error in the session panel.
- Missing `usage` on a response -> assistant message renders normally and usage chips stay hidden.
- Usage with no `cached_tokens` -> cache count is `0` and cache hit rate is `0%`.
- Streaming chunk with `usage: null` and content delta -> process content normally; only a non-empty final usage object updates usage telemetry.

### 5. Good/Base/Bad Cases

- Good: A streamed response ends with `{"choices": [], "usage": {"prompt_tokens": 20, "cached_tokens": 12}}`; the assistant message stores usage and the session total shows 12 cached reads.
- Good: Reloading `/static/index.html#chat` restores the active local session, model, preset, settings, messages, and usage totals.
- Base: A response without usage still displays content and stores the conversation; no usage chips are shown for that message.
- Bad: Removing `cached_tokens` in `normalize_usage()` hides cache-hit telemetry from both streaming and non-streaming Playground responses.
- Bad: Persisting uploaded file `data:` URLs for every historical message can exceed localStorage quota and make all session recovery fail.

### 6. Tests Required

- Backend response tests assert `normalize_usage()` and `sse_usage_chunk()` include `cached_tokens` and `prompt_tokens_details.cached_tokens`.
- Gemini metadata tests assert `cachedContentTokenCount` is derived from normalized cached tokens.
- Static frontend tests assert the local session key, create/restore/delete handlers, usage helpers, final SSE usage handling, session panel, usage panel, and absence of the Chat Settings dropdown.
- Browser smoke checks should cover desktop and mobile Playground layout after adding session and usage panels.
- WSL smoke checks should serve the static page and load the real accounts directory when API/static work changes.

### 7. Wrong vs Correct

#### Wrong

```python
def normalize_usage(usage=None):
	return {
		"prompt_tokens": usage.get("prompt_tokens", 0),
		"completion_tokens": usage.get("completion_tokens", 0),
		"total_tokens": usage.get("total_tokens", 0),
	}
```

This drops cache-read data already parsed from AI Studio wire usage, so the frontend cannot show cache hits.

#### Correct

```python
def normalize_usage(usage=None):
	cached_tokens = (usage or {}).get("cached_tokens", 0) or 0
	return {
		"prompt_tokens": (usage or {}).get("prompt_tokens", 0) or 0,
		"completion_tokens": (usage or {}).get("completion_tokens", 0) or 0,
		"total_tokens": (usage or {}).get("total_tokens", 0) or 0,
		"cached_tokens": cached_tokens,
		"prompt_tokens_details": {"cached_tokens": cached_tokens},
	}
```

The OpenAI-compatible shape remains backward-compatible while cache telemetry survives the backend-to-frontend boundary.
