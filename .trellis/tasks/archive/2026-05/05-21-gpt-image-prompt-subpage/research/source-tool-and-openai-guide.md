# Source Tool and OpenAI Guide Research

## Source Tool Findings

Source path: `C:/Users/bamboo/Desktop/GPT_image`.

The source is an Express + static JavaScript local OpenAI Responses workbench. It should not be copied as a service or dependency because this repository already provides a Python/FastAPI backend and a static Alpine UI.

Useful ideas to absorb:

- A focused image-workbench workflow with prompt, reference uploads, image parameters, history, and generated output in one screen.
- Image model settings for `gpt-image-2`: preset sizes, quality, background, output format, compression, and longer timeouts.
- Prompt templates for photorealistic, infographic, edit, and UI mockup use cases.
- Clear distinction between text-to-image generation and image editing with uploaded references.

Ideas not to copy directly:

- Node/Express backend, local JSON database, and local file store.
- Browser-side token/API URL inputs. This project already uses configured AI Studio accounts and its own OpenAI-compatible endpoints.
- Dark standalone three-column app shell. The new page should match this repo's current navigation and Alpine/static frontend patterns.

## OpenAI Image Prompting Guide Findings

Reference: https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide

Key patterns relevant to the new subpage:

- Prompts should be structured in a maintainable order: goal/use case, scene/background, subject, key details, composition, lighting/materials, and constraints.
- For complex prompts, labeled sections and line breaks are preferred over one long paragraph.
- Photorealistic workflows benefit from explicit `photorealistic` language, natural lighting, realistic textures, camera/framing cues, and avoidance of overly staged wording.
- Text-heavy artifacts such as infographics, slides, ads, labels, and UI mockups need exact quoted text, typography constraints, and medium/high quality.
- Edit workflows should state `Change only` and `Preserve exactly` invariants, repeating preservation constraints on each iteration to avoid drift.
- Multi-image workflows should reference input images by index and describe how they interact.
- For `gpt-image-2`, common production settings include `low`, `medium`, `high` quality and flexible sizes within model constraints. In this project, available sizes must still come from the current model metadata because the upstream AI Studio image models differ from OpenAI's direct image API.

## Mapping to This Repo

This repository already has:

- `/v1/images/generations` for OpenAI-compatible image generation.
- `/v1/images/prompt-optimizations` for prompt optimization using a selected text model.
- `/image-sessions` for image session history.
- `GeneratedImageStore` and static `/generated-images` serving.
- An existing `images` page that supports prompt templates, reference images, generated image display, history, and sessions.

Recommended implementation:

- Add a new focused subpage in the existing static Alpine app, not a separate Node app.
- Reuse existing image-generation methods and storage APIs where possible.
- Keep model/size controls driven by this repo's `/v1/models` capabilities rather than hard-coding OpenAI-only `gpt-image-2` constraints.
- Add richer prompt-building controls inspired by the OpenAI guide: workflow presets, structured fields, preserve/change blocks, quality hints, and one-click compose/optimize/generate actions.
- Add tests that verify the new route, navigation, key controls, and generated request payload behavior.
