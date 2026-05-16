# Image Prompt Templates And Optimization

## Goal

Improve the image generation page with style templates and a prompt optimization workflow. Users can choose an authoritative style template, optimize their raw prompt through a selectable text model, and pick one of three optimized prompt variants before generating images.

## What I Already Know

- The user wants selectable style templates such as realistic, comic, and no template, and asked us to provide authoritative options.
- The user wants prompt optimization after entering a raw prompt and choosing a style template.
- The optimizer model must be selectable and support a thinking switch.
- The optimizer should return 3 optimized prompt versions, each annotated with what is special about it.
- Current image UI is in `src/aistudio_api/static/index.html`, `src/aistudio_api/static/app.js`, and `src/aistudio_api/static/style.css`.
- Current backend already supports OpenAI-compatible chat/image endpoints, model metadata, model capabilities, and thinking controls.

## Research References

- [`research/image-prompt-guidance.md`](research/image-prompt-guidance.md) — official Google/OpenAI image prompting guidance mapped to project templates.

## Requirements

- Add a style template selector to the image generation form.
- Provide a compact authoritative template list derived from official prompting categories: no template, photorealistic, comic, digital art, watercolor, oil painting, anime, 3D render, and pixel art.
- Keep image generation optional and backwards compatible: users can still type a prompt and generate without optimizing.
- Add an optimizer panel/action on the image page.
- Let users choose the prompt optimization model from text-capable models that are not image-output models.
- Let users choose optimizer thinking level: off, low, medium, high; normalize to off when the chosen model does not support thinking.
- Add a backend prompt optimization endpoint that accepts raw prompt, style template, optimizer model, and thinking setting.
- The optimizer response must include exactly 3 variants with title, special note, and optimized prompt.
- Let the user apply one optimized prompt variant into the main image prompt.
- Show loading and error states for optimization.
- Preserve current image generation, image references, sessions, and history behavior.

## Acceptance Criteria

- [ ] Image page exposes selectable style templates including no template, photorealistic, and comic.
- [ ] Image page exposes optimizer model selection and thinking control.
- [ ] Clicking optimize calls a backend endpoint with prompt, style template, model, and thinking.
- [ ] Optimizer results render 3 variants and each variant has a special note.
- [ ] Applying a variant replaces the image prompt with the optimized prompt.
- [ ] Backend validates prompt, style template, optimizer model, and thinking.
- [ ] Backend forwards thinking to chat handling for text models that support it.
- [ ] Unit/static tests cover the new UI and backend contract.
- [ ] Real WSL environment test passes for this code/API/frontend change.

## Definition Of Done

- Tests added/updated for backend and static frontend behavior.
- Relevant unit tests pass locally.
- Real WSL test passes using a temporary directory under `/home/bamboo` as required by project instructions.
- Task files, code, and tests are committed on the feature branch.

## Out Of Scope

- No custom user-defined style template persistence.
- No image-generation model native `style` parameter, because current AI Studio image models reject/ignore OpenAI image style fields.
- No streaming prompt optimization.
- No multilingual optimizer UI beyond current Chinese interface text.

## Technical Approach

- Add static style template metadata in the frontend with labels, descriptions, and style hints.
- Add frontend state for `imageStyleTemplate`, `imagePromptOptimizerModel`, `imagePromptOptimizerThinking`, `imagePromptOptimizing`, `imagePromptOptimizeError`, and `imagePromptOptions`.
- Add `/v1/images/prompt-optimizations` to OpenAI-compatible routes.
- Reuse `handle_chat` with a JSON schema response format so the gateway asks the selected text model for 3 prompt variants.
- Add robust fallback parsing so valid JSON embedded in text can still be read.
- Add static tests and API service tests for UI exposure and backend optimization behavior.