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