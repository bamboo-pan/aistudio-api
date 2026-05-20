# fix: prompt optimizer includes selected image materials

## Goal

Prompt optimization for image generation must consider the same selected image materials that will be sent during generation/editing, so optimized prompts stay aligned with the user's chosen base image and reference images.

## What I already know

* The user reported that the prompt optimizer currently targets only the text prompt and does not send selected image materials.
* The image workspace already tracks selected materials in `imageBaseImage` and `imageReferences`.
* `imageEditReferences` combines base image plus references, and `imageRequestImages()` converts those items to request-ready image data for image generation.
* `optimizeImagePrompt()` currently posts only `prompt`, `style_template`, `model`, and `thinking` to `/v1/images/prompt-optimizations`.
* Backend `ImagePromptOptimizationRequest` currently has no `images` field.
* Backend `handle_image_prompt_optimization()` builds a text-only `ChatRequest` for the optimizer model.

## Requirements

* The frontend prompt optimizer request must include the currently selected base image and reference images when they exist.
* The frontend must reuse the existing image material conversion behavior so uploaded, generated, and same-origin images are handled consistently with image generation.
* The backend prompt optimization API must accept optional image inputs using the same compatible input shape as image generation (`data:` URLs, HTTP(S) URLs, or `{url}` objects).
* The backend must include reference image parts in the optimizer model request when the chosen optimizer model supports image input.
* If images are supplied but the optimizer model does not support image input, the API must reject the request clearly before calling the upstream client.
* Existing text-only optimization behavior must remain unchanged when no images are selected.
* Structured JSON output parsing and thinking behavior must remain unchanged.

## Acceptance Criteria

* [ ] Optimizing with no selected images sends a text-only optimization request and still returns three options.
* [ ] Optimizing with selected images sends those images to `/v1/images/prompt-optimizations` from the frontend.
* [ ] Backend optimizer calls include the original optimization text plus image parts in the user message content.
* [ ] Backend rejects image-bearing optimization requests for text models without image input support.
* [ ] Unit/static tests cover the new request field and frontend payload behavior.
* [ ] Static JS syntax check passes.

## Definition of Done

* Relevant unit tests pass.
* `node --check src/aistudio_api/static/app.js` passes after editing the static frontend.
* Real WSL API and frontend smoke tests pass because this changes API and UI behavior.
* Task files remain committed with the code changes.

## Out of Scope

* Changing the visual layout of the prompt optimizer panel.
* Generating captions/descriptions for reference images before optimization.
* Changing image generation/editing request behavior.

## Technical Notes

* Data flow: selected frontend materials -> `imageRequestImages()` -> `images` field on prompt optimization request -> backend schema -> optimizer chat message content list containing text and image URL blocks -> existing chat normalization/gateway path.
* Keep validation at the backend entry/service boundary, matching existing image generation validation behavior.
* Use existing request-image helpers rather than introducing a separate image fetch/temporary-file path for optimizer requests.