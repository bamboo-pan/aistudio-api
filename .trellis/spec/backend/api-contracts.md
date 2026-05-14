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
- Static frontend tests that account management exposes `exhaustion` and resolution usage UI.
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