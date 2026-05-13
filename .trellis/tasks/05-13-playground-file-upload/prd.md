# playground: model-based file upload

## Goal

Enable Playground file uploads only when the selected model supports the relevant input modality, including generic non-image files for models that can accept file inputs.

## What I Already Know

* The Playground chat UI is implemented in `src/aistudio_api/static/index.html`, `src/aistudio_api/static/app.js`, and `src/aistudio_api/static/style.css`.
* Model metadata is returned from `/v1/models` and each model includes a `capabilities` object from `src/aistudio_api/domain/model_capabilities.py`.
* Existing backend chat normalization supports OpenAI `image_url` content blocks and Gemini `inlineData` for image data.
* The AI Studio wire layer already has a generic `inline_data` part shape, so non-image files can be carried as MIME-tagged inline data without adding a server-side upload store.
* Existing backend code explicitly rejects Gemini `fileData`; remote file URI support is separate from local Playground uploads.
* Registered model metadata already distinguishes `image_input` from text-only models.

## Assumptions

* In this task, "upload files" means local browser-selected files encoded as inline data URLs and forwarded through chat/generate-content requests.
* Remote file URI upload (`fileData.fileUri`) and durable server-side file storage are not required for this PR.

## Requirements

* Model metadata must expose whether generic file input is supported and which MIME types or MIME wildcards the model accepts.
* The Playground must derive upload availability and accepted file types from the selected model's capabilities.
* For models with file input support, the Playground must enable local file attachments including images and supported non-image files.
* For models without file input support, the upload control must be disabled and prevent queued attachments from being sent.
* When switching from a file-capable model to a non-file-capable model while attachments are queued, the UI must show a clear error state and block sending until attachments are removed or the model changes.
* The request sent to `/v1/chat/completions` must include uploaded images as OpenAI-compatible `image_url` content blocks and uploaded non-image files as file content blocks with data URLs.
* Backend chat normalization must accept OpenAI-compatible file content blocks and Gemini `inlineData` for supported MIME types.
* Backend validation must reject file inputs for models that do not advertise file input support.
* Static and unit tests should cover model-capability-based upload behavior and backend request normalization.

## Acceptance Criteria

* [ ] A model with file input support enables the Playground upload button and accepts supported file types.
* [ ] A model without file input support disables the upload button and cannot send attachments.
* [ ] Model switching re-evaluates upload support and accepted MIME types immediately.
* [ ] Uploaded images are previewed before send and included in the outgoing chat request as `image_url` blocks.
* [ ] Uploaded non-image files are shown as file attachments before send and included as file content blocks.
* [ ] Backend chat normalization forwards supported file data as AI Studio inline data.
* [ ] Backend validation rejects file uploads for models without file input support.
* [ ] Existing image generation behavior remains unchanged.
* [ ] Unit/static tests pass for frontend capability metadata, upload control wiring, and request normalization.

## Definition of Done

* Tests added or updated for the changed behavior.
* Project lint/type/test checks run as appropriate.
* Unsupported MIME types are rejected before downstream replay.
* Trellis spec-update gate reviewed before finishing.

## Technical Approach

Use the existing `/v1/models` metadata as the source of truth. Add a generic file-input capability with accepted MIME type metadata, update the Playground to use that metadata for the file picker, and extend request normalization to convert local file data URLs into AI Studio inline data. Preserve existing image attachment compatibility by continuing to emit `image_url` blocks for image files.

## Decision (ADR-lite)

**Context**: The user wants Playground uploads to be enabled only when the model supports them and selected option 3: full generic file upload support.

**Decision**: Add generic file upload support for local inline files. Gate the UI and backend by model file-input capabilities and accepted MIME types.

**Consequences**: The UI can expose PDF/document/media-style local attachments for capable models while still blocking unsupported models. Remote Gemini `fileData` and server-side file storage remain separate follow-up work.

## Out of Scope

* Remote Gemini `fileData.fileUri` support.
* Server-side file persistence or multipart upload endpoints.
* Uploading files directly to Google Drive/File API from this proxy.
* Changes to image generation models or image history.

## Technical Notes

* Relevant source files inspected: static Playground files, model capability registry, OpenAI-compatible routes, chat request schemas, chat normalization service, static frontend tests.
* Existing backend size guard for inline images is 20 MB; the same guard should apply to local inline file data unless changed explicitly.
* Existing tests already include static assertions around `selectedCaps.image_input`, image upload wiring, and image generation page behavior; they need expansion for generic file capability metadata.

## Open Questions

* None. User selected option 3 and requested implementation on a feature branch.
