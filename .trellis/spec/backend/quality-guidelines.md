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
