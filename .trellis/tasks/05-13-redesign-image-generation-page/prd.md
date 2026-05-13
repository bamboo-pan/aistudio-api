# Redesign Image Generation Page

## Goal

Completely redesign the image generation page so users can generate, edit, compare, reuse, and manage generated images without fighting the layout. Keep all core generation behavior and backend API contracts unchanged.

## What I Already Know

* The current UI is a static Alpine.js app using `src/aistudio_api/static/index.html`, `app.js`, and `style.css`.
* The current image page already supports prompt input, model selection, size, count, response format, reference uploads, base image editing, results, local history, downloads, retries, deletion, and an edit conversation log.
* The generation call is already implemented through `/v1/images/generations` in `generateImage()` and should remain functionally unchanged.
* Existing tests assert that the static frontend exposes image upload, generation, history, retry, delete, keyboard select behavior, and avoids storing `b64_json` in lightweight history items.
* The screenshot shows poor spatial balance: the form is narrow, results are visually disconnected, conversation/history compete for attention, and the empty states do not guide the user.

## Assumptions

* This is a UX/layout refactor, not a backend feature task.
* The target user is an operator/developer using the page repeatedly for real image generation and iteration, so the UI should prioritize clarity, density, fast reuse, and visible feedback over marketing-style presentation.
* Existing Chinese UI text should remain Chinese.

## Requirements

* Redesign the image page information architecture as a guided Studio workflow: compose prompt, attach references or a base image, choose parameters, generate, then review and reuse outputs.
* Preserve current core functions and API behavior: prompt, model, size, count, response format, references, base image, edit session, results, history, retry, download, delete.
* Make the primary generation flow obvious: prompt area, generation button, active model/size/count, reference/base images, busy/error states, and retry should be visible and coherent.
* Improve empty states with useful prompts and visible affordances instead of isolated `暂无结果` / `暂无会话` boxes.
* Make generated results prominent after the guided setup, with larger previews and actions that are easy to scan.
* Keep local history useful but visually secondary to current results.
* Preserve existing custom select keyboard/scroll behavior and responsive support.
* Ensure mobile layout remains usable with no overlapping text or controls.

## Acceptance Criteria

* [ ] The image page starts with a clear guided Studio workflow, not separate disconnected cards.
* [ ] Users can upload references, set/clear a base image, start a new edit session, and understand current edit context at a glance.
* [ ] Generated results show large enough previews and expose download, set as base, add reference, retry, and delete actions.
* [ ] History still supports selection, batch reference, batch download, batch delete, clearing, and per-image actions.
* [ ] Loading, error, empty, and no-model states are visually distinct and actionable.
* [ ] Existing `/v1/images/generations` request shape remains unchanged except for UI-driven existing values.
* [ ] Existing static frontend tests pass or are updated only to reflect new markup/class names while preserving behavior checks.
* [ ] The page works on desktop and mobile viewports without incoherent overlap or clipped button text.
* [ ] Real WSL environment testing is completed per repository instructions.

## Definition of Done

* Tests added or updated where markup expectations change.
* Python test suite relevant to frontend/image behavior passes locally.
* Page is manually verified in a browser with responsive checks.
* WSL real environment validation is performed.
* Trellis check and spec-update gates are completed.
* Work is committed with Trellis task records and pushed to the remote branch.

## Open Questions

* Which UX direction should the redesign follow for the MVP?

## Technical Approach

Candidate approaches:

**Approach A: Production Workspace (recommended)**

* A dense, tool-like image workspace with a wide prompt composer at the top/left, a dominant result canvas/gallery, and compact side rails for edit context and history.
* Best fit for repeated operational use and for preserving existing functions without inventing new product scope.

**Approach B: Guided Studio (chosen)**

* A more step-by-step layout: prompt -> references -> settings -> generate -> result review.
* Easier for first-time users while still keeping history/actions visible enough for repeated iteration.

**Approach C: Gallery-first Review Board**

* Prioritize current results and history as a masonry/review board, with the prompt composer as a sticky utility panel.
* Strong for comparing outputs, but may make setup and edit context less obvious.

## Expansion Sweep

## Decision (ADR-lite)

**Context**: The current image page exposes the right capabilities but does not explain the generation/editing workflow, so users must infer how prompt, references, base image, results, conversation, and history connect.

**Decision**: Use the Guided Studio direction for MVP. Organize the page around explicit stages: prompt, references/edit context, parameters, generation, result review, and reuse/history.

**Consequences**: The redesign favors clarity and onboarding over a purely dense power-user board. To avoid slowing repeat users down, key actions such as retry, set as base, add reference, download, delete, and batch history actions must remain one click away where practical.

### Future Evolution

* The page could later add prompt presets, seed/style controls, comparison modes, or model-specific advanced settings.
* The layout should leave room for extra parameter controls without rewriting the main structure.

### Related Scenarios

* Chat file upload and image reference upload should keep consistent thumbnail/remove/error behavior.
* Generated results and history should keep action parity where possible.

### Failure And Edge Cases

* No image-capable model, model loading failure, generation failure, reference file errors, deletion failures, and empty history/results all need clear UI states.
* Large filenames/prompts/model names must not break layout.

## Out of Scope

* Changing backend image generation, account rotation, model capability metadata, or generated image storage.
* Adding new generation parameters not already exposed by model metadata.
* Replacing Alpine.js or introducing a frontend build system.
* Adding cloud sync or server-side history beyond existing generated image storage.

## Technical Notes

* Relevant files: `src/aistudio_api/static/index.html`, `src/aistudio_api/static/app.js`, `src/aistudio_api/static/style.css`, `tests/unit/test_static_frontend_capabilities.py`.
* Keep `generateImage()` API behavior stable: `model`, `prompt`, `size`, `n`, `response_format`, and optional `images` are already implemented.
* Current image tests include literal CSS checks, so class-level refactors may require updating behavior-preserving assertions.
