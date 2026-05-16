# Refine Playground Sidebar And Message Actions

## Goal

Improve the chat playground so repeated request/token details do not crowd the workbench, the right-side tools can collapse like the primary navigation, and each conversation turn exposes common editing and branching actions shown in the reference screenshots.

## What I Already Know

* The chat playground lives in `src/aistudio_api/static/index.html`, `app.js`, and `style.css`.
* The existing layout repeats model/request/attachment/token information in the top metrics, input metadata, and right-side request/usage panels.
* The left sidebar already has persisted collapse state through `sidebarCollapsed` and `aistudio.sidebarCollapsed`.
* Existing local chat sessions are stored in `localStorage` under `aistudio.chatSessions.v1`.
* Existing tests inspect static frontend capabilities in `tests/unit/test_static_frontend_capabilities.py`.

## Requirements

* Remove or consolidate duplicated chat summary information so the same model/request/token data is not shown in multiple prominent places.
* Make the right playground side rail collapsible with a persisted preference, mirroring the left navigation behavior.
* Keep the right rail usable when collapsed by showing compact icon buttons/labels for the major sections.
* Add per-message operations inspired by the screenshots:
  * Edit a user message and rerun the conversation from that turn.
  * Rerun from the nearest preceding user turn for an assistant response.
  * Delete an individual turn.
  * Branch from a turn into a new local chat session containing messages up to that point.
  * Copy as plain text and copy as Markdown.
  * Make this an app by creating a focused app-generation turn from the selected message.
* Preserve existing local-session save/restore behavior.
* Keep the implementation in the static frontend without adding new dependencies.

## Acceptance Criteria

* [ ] Chat playground no longer renders both top metrics and a separate request summary with the same information.
* [ ] Right playground rail has a collapse/expand control and persists its state in localStorage.
* [ ] Collapsed right rail remains visually stable on desktop and does not break the mobile layout.
* [ ] Message actions are available from visible controls/menus and update the local conversation/session as expected, including the app-generation shortcut.
* [ ] Static frontend tests cover the new collapse and message action hooks.
* [ ] Relevant unit tests pass.

## Definition Of Done

* Tests added/updated where appropriate.
* Frontend behavior manually or automated checked at desktop/mobile sizes where feasible.
* No unrelated refactors.
* Trellis task metadata is committed with the implementation.

## Out Of Scope

* Backend APIs for server-side chat session branching.
* Full rich text editor for messages.
* Authentication, account rotation, image generation, or gateway changes.

## Technical Notes

* Reuse the current Alpine-style state object and localStorage helpers.
* Use existing CSS visual language: restrained operational UI, 8px radius, compact controls.
* The right rail should prefer stable width transitions over reflow-heavy interactions.