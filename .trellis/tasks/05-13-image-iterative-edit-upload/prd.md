# Image Generation Iterative Editing and Upload Support

## Goal

Turn the existing image generation page from a single-turn generator into an iterative image editing workspace: users can keep conversing with the AI to refine generated images, and can upload one or more local images as editing/reference inputs.

## What I Already Know

* The current image page can generate images, retry a prompt, download/delete results, and store lightweight local history.
* The current `retryImage` flow only restores a previous prompt/model/size and starts a fresh generation; it does not send the previous image back as input.
* The chat page already supports local image upload as OpenAI `image_url` data URLs for multimodal chat models.
* Image-capable models in the registry expose both `image_input` and `image_output`, so the model metadata can support edit UX gating.
* Backend chat/Gemini normalization already knows how to convert inline image data to AI Studio wire content.
* `/v1/images/generations` currently accepts only OpenAI image-generation style fields and forbids extra fields, so image editing needs an explicit API shape rather than silently overloading unknown fields.
* Pure HTTP mode intentionally does not support image generation/multimodal paths; this feature should remain browser-mode only.

## Assumptions (Temporary)

* The feature should live primarily in the existing 图片生成 page, not replace the Playground chat page.
* Editing should use the existing AI Studio replay path and image model capabilities rather than adding an unrelated image provider.
* Uploaded images should be treated as request inputs and not persisted server-side unless they are also generated outputs.

## Open Questions

* None.

## Requirements (Evolving)

* Users can upload image files from the image page for AI image editing/reference.
* Users can use a generated/history image as the source for a follow-up edit instead of only regenerating from text.
* Users can continue a visible editing conversation so each instruction/result is part of the working context.
* Users can attach multiple reference/style images in an editing turn.
* The image page MVP is a conversation-style editing workspace rather than only a one-shot edit form.
* Multi-turn editing automatically carries forward pinned reference/style images and uses the latest generated result as the next base image.
* Users can remove pinned reference images when they should no longer influence later turns.
* Generated edit outputs continue to appear in the result/history flows with download and delete support.
* The UI must clearly distinguish fresh generation from editing an existing/uploaded image.
* Requests must validate unsupported inputs and produce friendly API errors.

## Acceptance Criteria (Evolving)

* [ ] The image page exposes upload controls for edit/reference images.
* [ ] A generated or history image can be sent back as an edit source with a new instruction.
* [ ] Multiple uploaded/history/result images can be attached as references for one edit request.
* [ ] Multiple edit turns can be made without manually re-uploading the latest generated image each time.
* [ ] Pinned references persist across edit turns until removed, and the newest generated image becomes the next default base image.
* [ ] The backend sends image input plus text instruction to the image-capable model and returns generated image output through the existing persistence response shape.
* [ ] Unsupported models, missing prompt, invalid image data, oversized images, and pure HTTP unsupported mode are handled with clear errors.
* [ ] Existing single-turn image generation behavior remains available.
* [ ] Unit/static frontend tests cover the new request shape and UI hooks.
* [ ] Real WSL environment test passes before final completion.

## Definition of Done

* Tests added/updated for backend image edit request handling and frontend affordances.
* Existing image generation tests remain green.
* Lint/type/check commands relevant to the project pass.
* The change is exercised in the real WSL test environment per project instructions.
* Docs/spec notes updated if implementation reveals durable conventions.

## Decision (ADR-lite)

**Context**: The initial image page only supports fresh generation and prompt retry, but the desired workflow is iterative visual refinement with uploaded/reference images.

**Decision**: Build the MVP as a conversation-style image editing workspace with multi-image reference support. Users can upload images, select generated/history images, and continue editing from prior outputs.

**Consequences**: The frontend needs explicit editing-session state and the backend needs an image-edit request path that sends text plus inline images to the image-capable AI Studio model. This is larger than a one-shot edit form, but it preserves the workflow users expect for iterative visual work.

## Reference Carry-Forward Decision

Pinned uploaded/history/style reference images persist across follow-up edit turns until the user removes them. The newest generated image from the current edit session automatically becomes the next base image, so users can keep refining without manually re-attaching it.

## Technical Notes

* Likely frontend files: `src/aistudio_api/static/app.js`, `src/aistudio_api/static/index.html`, `src/aistudio_api/static/style.css`.
* Likely backend files: `src/aistudio_api/api/schemas.py`, `src/aistudio_api/application/api_service.py`, `src/aistudio_api/infrastructure/gateway/client.py`.
* Existing tests to extend: `tests/unit/test_image_generation_service.py`, `tests/unit/test_static_frontend_capabilities.py`.
* Existing image output persistence lives in `GeneratedImageStore` and the `/generated-images` static/delete route.
* Existing chat upload uses data URLs and enforces a 20 MB per-image frontend limit.

## Out of Scope (Draft)

* Mask/brush inpainting UI.
* Server-side uploaded-image asset library.
* Collaborative/multi-user image sessions.
* Pure HTTP image editing support.
