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

---

## Testing Requirements

<!-- What level of testing is expected -->

(To be filled by the team)

---

## Code Review Checklist

<!-- What reviewers should check -->

(To be filled by the team)

---

## Scenario: Image Edit Inputs on `/v1/images/generations`

### 1. Scope / Trigger

- Trigger: cross-layer API contract change between the static image page, the OpenAI-compatible image route, application service validation, and AI Studio gateway replay.
- Applies when adding or changing image generation fields that carry image input/reference data.

### 2. Signatures

- API: `POST /v1/images/generations`
- Schema: `ImageRequest(prompt: str, model: str, n: int, size: str, response_format: str | None, images: list[str | {url: str}] | None)`
- Gateway: `AIStudioClient.generate_image(..., images: list[str] | None = None)` where `images` are local temporary file paths created by the service layer.

### 3. Contracts

- `images` is optional. Omitted or empty means fresh text-to-image generation.
- Each `images[]` item must be a data URI, HTTP(S) URL, or object with `url` containing one of those values.
- The frontend should submit generated/history/local reference images as data URIs so the backend does not need to resolve same-origin static routes.
- The service layer converts accepted image URLs to temporary files, passes those paths to the gateway, and always deletes them after success or failure.
- The gateway converts paths into `AistudioPart.inline_data` and rewrites the captured request with explicit `contents`.
- Response shape remains the existing OpenAI-compatible image response with persisted `url`, `b64_json`, `path`, `delete_url`, `mime_type`, and `size_bytes` fields.

### 4. Validation & Error Matrix

- Missing/blank `prompt` -> `400 bad_request`.
- Non-image model -> `400 bad_request`.
- Unsupported `size` -> `400 bad_request`.
- Unsupported OpenAI image fields -> `400 bad_request` listing supported fields including `images`.
- `images` has more than 10 items -> `400 bad_request`.
- `images[]` is empty or has no URL -> `400 bad_request`.
- `images[]` is not data URI or HTTP(S) URL -> `400 bad_request`.
- Invalid base64 or oversized image data -> `400 bad_request` from shared image decoding validation.
- AI Studio returns no image data -> upstream `502`.

### 5. Good/Base/Bad Cases

- Good: `prompt + images: ["data:image/png;base64,..."]` produces persisted image output and cleans the temporary input file.
- Base: `prompt` only continues to produce fresh image generations with no `images` argument passed to the gateway.
- Bad: `images: ["/generated-images/a.png"]` is rejected; frontend must convert same-origin images to data URIs before sending.

### 6. Tests Required

- Unit test that data URI image inputs are passed to `generate_image(images=...)` and temporary files are cleaned.
- Unit test that invalid image URLs fail before client calls.
- Regression tests that prompt-only image generation still calls the gateway without `images`.
- Static frontend test that upload/reference/session controls and `body.images` request wiring exist.

### 7. Wrong vs Correct

#### Wrong

```json
{"prompt":"edit this","images":["/generated-images/20260513/a.png"]}
```

The backend should not infer local static files from relative URLs in this contract.

#### Correct

```json
{"prompt":"edit this","images":["data:image/png;base64,..."]}
```

The frontend fetches same-origin images and submits data URIs; the backend validates and converts them to temporary inline image inputs.

---

## Scenario: Static Playground Workbench UI

### 1. Scope / Trigger

- Trigger: redesigning or extending the static Playground chat page served from `src/aistudio_api/static/`.
- Applies to `index.html`, `app.js`, `style.css`, and static frontend tests that protect Playground behavior.
- This scenario is UI-only unless the task explicitly changes an API route or schema.

### 2. Signatures

- Static app state: Alpine `app()` object owns Playground state and derived getters.
- Existing backend calls remain:
	- `GET /v1/models` for model metadata and capabilities.
	- `POST /v1/chat/completions` for chat requests.
- Existing chat content block format remains unchanged:
	- Text-only messages may send a string content value.
	- Image files use OpenAI `image_url` blocks.
	- Non-image files use OpenAI `file` blocks with `file_data`, `filename`, and `mime_type`.

### 3. Contracts

- UI enhancements must not change `/v1/chat/completions` request fields unless the API contract spec is updated in the same task.
- Capability gating must continue to use `/v1/models` metadata through `selectedCaps` and `controlAvailable(...)`.
- `file_input=false` must keep upload controls disabled and must not create a path where generic files can be submitted.
- Workbench-only helpers such as prompt templates, request summaries, presets, copy actions, and clear-chat actions must stay frontend-local.
- Assistant Markdown rendering must be frontend-only and must pass model text through a local escape/sanitize helper before any `x-html` binding; raw model HTML must render as text and unsafe link schemes must not become anchors.
- Static markup may be reorganized, but existing behavior anchors used by tests must be preserved or intentionally replaced with updated tests.

### 4. Validation & Error Matrix

- Missing or failed model metadata -> show the existing model loading error path; do not enable controls that depend on unknown capabilities.
- Unsupported file input -> keep upload disabled and preserve the `当前模型不支持文件输入` feedback path.
- Empty prompt with no files -> send button remains disabled.
- Runtime preset applied to unsupported controls -> unsupported values are ignored or normalized through `applyModelCapabilities()`.
- Model output contains raw HTML or unsafe Markdown links -> escaped text is displayed, not trusted HTML or executable links.
- Narrow viewport -> primary input, send, attachment controls, and side panels must not overlap.

### 5. Good/Base/Bad Cases

- Good: A prompt template fills `draft`, request summary updates from current model/config/files, and the existing send path builds the same request body as before.
- Good: A parameter preset updates only controls available for the selected model, then runs `applyModelCapabilities()`.
- Base: Existing topbar settings dropdown still controls advanced chat settings after the Playground layout changes.
- Bad: A UI redesign duplicates file validation logic and lets non-file-capable models submit generic file blocks.
- Bad: A static layout looks correct on desktop but overlaps the chat panel and side panels on a mobile viewport.

### 6. Tests Required

- Static frontend tests assert new Playground helpers and markup anchors exist.
- Markdown output changes must test the `x-html` rendering hook plus HTML escaping and unsafe-link sanitization helpers.
- Existing static tests must continue to assert `selectedCaps`, `controlAvailable(...)`, `chatCanSend`, `chatFileAccept`, and file block request wiring.
- Full unit tests should pass after static UI changes because the frontend is coupled to request contracts through string-level tests.
- Browser smoke checks should include desktop and mobile viewport inspection for workbench layout changes.

### 7. Wrong vs Correct

#### Wrong

```javascript
applyChatPreset(name){
	this.cfg.temperature = 1.4
	this.cfg.thinking = 'medium'
}
```

This writes settings even when the selected model does not support those controls.

#### Correct

```javascript
applyChatPreset(name){
	if(this.controlAvailable('temperature')) this.cfg.temperature = 1.4
	if(this.controlAvailable('thinking')) this.cfg.thinking = 'medium'
	this.applyModelCapabilities()
}
```

This keeps presets consistent with model metadata and the existing capability gating contract.
