# Playground Output Markdown Rendering

## Goal

Add safe Markdown rendering support to the Playground chat output so assistant responses with headings, lists, code blocks, links, and emphasis are readable without changing chat request or response APIs.

## What I Already Know

* The user asked for Markdown rendering support in Playground output.
* The Playground chat UI is static Alpine code under `src/aistudio_api/static/`.
* Assistant response content is stored in `m.content` for both streaming and non-streaming responses.
* The current message body uses `x-text="m.error||m.content"`, so all output is rendered as plain text.
* Existing static frontend tests protect Playground anchors in `tests/unit/test_static_frontend_capabilities.py`.

## Requirements

* Render assistant chat message content as Markdown in the Playground transcript.
* Preserve streaming behavior: partial assistant content should continue updating as tokens arrive.
* Keep user prompts, error messages, and thinking blocks safe and readable without interpreting them as Markdown unless explicitly needed later.
* Escape raw HTML before rendering Markdown-derived HTML so model output cannot inject scripts or arbitrary HTML.
* Sanitize Markdown links so unsafe schemes such as `javascript:`, `vbscript:`, and `data:` are not emitted as clickable links.
* Keep copy behavior unchanged: copying a message should copy the raw original text, not rendered HTML.
* Do not change `/v1/chat/completions` request or response contracts.
* Avoid external network dependencies or a build pipeline change; the static app should remain self-contained.

## Acceptance Criteria

* [ ] Assistant output supports common Markdown blocks: paragraphs, headings, ordered/unordered lists, blockquotes, fenced code blocks, inline code, emphasis, and links.
* [ ] Raw HTML in model output is displayed as text, not executed or inserted as trusted markup.
* [ ] Unsafe Markdown link schemes are not emitted as clickable anchors.
* [ ] Existing Playground controls, file attachment behavior, streaming, and copy action remain intact.
* [ ] Static frontend tests are updated for the Markdown rendering hooks and safety guards.
* [ ] Relevant pytest checks pass.

## Definition of Done

* Tests added or updated where behavior changes.
* Project checks pass for the touched area.
* No API contract changes are introduced.
* Trellis check and spec-update gates are completed.

## Technical Approach

Implement a small local, safe Markdown renderer inside the existing Alpine `app()` object. The renderer will first escape untrusted text, then transform a limited Markdown subset into HTML. The transcript message body will switch from `x-text` to `x-html` through a single helper that decides whether to render Markdown or plain escaped text based on message role and error state. CSS will style rendered Markdown inside the existing message body without changing the Playground layout.

## Decision (ADR-lite)

**Context**: The app is a self-contained static frontend with no bundler. Pulling a browser Markdown dependency from a CDN would add an external runtime dependency, while vendoring a full parser is larger than this task needs.

**Decision**: Use a small local renderer for a safe, common Markdown subset and explicitly sanitize raw HTML and links.

**Consequences**: The renderer will not be a complete CommonMark implementation, but it covers the model-output formatting users expect while keeping the static app simple and avoiding a new supply-chain surface.

## Out of Scope

* Full CommonMark compliance.
* Math, Mermaid, tables, footnotes, task lists, or syntax highlighting.
* Markdown rendering for image-generation history, account pages, or thinking blocks.
* Backend API/schema changes.

## Technical Notes

* Relevant UI files: `src/aistudio_api/static/index.html`, `src/aistudio_api/static/app.js`, `src/aistudio_api/static/style.css`.
* Relevant tests: `tests/unit/test_static_frontend_capabilities.py`.
* Relevant spec: `.trellis/spec/backend/quality-guidelines.md` scenario "Static Playground Workbench UI".