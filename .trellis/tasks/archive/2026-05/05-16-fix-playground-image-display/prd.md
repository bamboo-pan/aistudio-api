# Fix Playground Image Display

## Goal

Playground assistant messages should display generated image Markdown as visible images instead of plain links, so image-capable chat models can be inspected directly in the transcript.

## Requirements

* Render assistant Markdown image syntax like `![generated image 1](/generated-images/example.png)` as an `<img>` in the Playground transcript.
* Keep existing safe Markdown behavior: escape normal text, keep user messages as plain text, and reject unsafe Markdown URLs.
* Preserve normal Markdown links as links.
* Add/update focused static frontend coverage for image Markdown rendering.

## Acceptance Criteria

* [ ] A chat image-model response containing `![generated image 1](/generated-images/*.png)` produces an image element in Playground assistant messages.
* [ ] Unsafe image URLs such as `data:` or `javascript:` are not emitted as image sources.
* [ ] Existing link, code, paragraph, and user-message behavior stays intact.
* [ ] Relevant unit tests pass.

## Definition of Done

* Tests added or updated for the frontend rendering contract.
* Targeted unit tests pass locally.
* WSL real-environment test is run if feasible for the final verification path.
* No unrelated refactors or behavioral changes.

## Technical Approach

Extend the existing lightweight Markdown renderer in `src/aistudio_api/static/app.js` so image tokens are parsed before normal link tokens and restored after escaping, using the existing `safeMarkdownUrl()` and `escapeHtml()` helpers. Add CSS for generated images inside `.markdown-body` so transcript images are visible, bounded, and click/open friendly without disrupting text layout.

## Decision (ADR-lite)

**Context**: The backend already returns image-model chat content as Markdown image syntax, and the Playground recently added safe Markdown rendering for assistant replies.
**Decision**: Keep the local renderer and add first-class image Markdown support rather than adding a Markdown dependency.
**Consequences**: The fix remains small and dependency-free, but the renderer continues to support only the Markdown subset needed by this UI.

## Out of Scope

* Changing backend image generation response format.
* Adding a full Markdown parser dependency.
* Redesigning the Playground transcript or image generation studio.

## Technical Notes

* `tests/unit/test_image_generation_service.py` expects image-model chat responses to start with `![generated image 1](/generated-images/`.
* `src/aistudio_api/static/app.js` currently parses inline code and normal links in `renderMarkdownInline()`.
* `src/aistudio_api/static/index.html` already renders assistant message bodies with `x-html="messageBodyHtml(m)"`.
* `tests/unit/test_static_frontend_capabilities.py` contains static contract tests for the frontend Markdown renderer.
