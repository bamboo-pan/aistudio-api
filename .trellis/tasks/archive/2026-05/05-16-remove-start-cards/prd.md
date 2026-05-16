# Remove Unused Start Cards

## Goal

Remove the empty-chat start prompt area shown in the Playground transcript because the user does not use it.

## Requirements

* When the Playground chat has no messages, do not show the `RUN` badge, the `Choose a starting point` heading, or the four prompt template cards.
* Remove the now-unused prompt template state, fill-template action, and CSS for the removed card grid.
* Preserve the existing chat input, model selection, session persistence, attachment handling, and send flow.
* Keep the empty transcript area visually stable and uncluttered on desktop and mobile.

## Acceptance Criteria

* [x] The screenshoted empty-chat start cards are no longer rendered.
* [x] No references remain to the removed prompt templates or template click handler.
* [x] Static frontend tests pass or are updated to reflect the intentional removal.
* [x] Full unit tests pass for the repository.

## Definition of Done

* Tests relevant to the static frontend are run.
* Full unit tests are run if feasible.
* Browser/UI smoke check verifies the empty chat no longer displays the removed content.
* Task files and implementation changes are committed together.

## Technical Approach

Edit the static Playground files only: remove the empty-state template block from `index.html`, remove `chatTemplates` and `usePromptTemplate` from `app.js`, remove the specific CSS selectors in `style.css`, and update any static tests that assert those anchors exist.

## Decision (ADR-lite)

**Context**: The existing empty chat state offers convenience prompt cards that the user no longer wants.
**Decision**: Remove the cards and their supporting local frontend helpers instead of hiding them with CSS.
**Consequences**: The Playground starts with a cleaner blank transcript while existing input and chat behavior remain unchanged.

## Out of Scope

* Redesigning the full Playground layout.
* Changing chat request bodies or backend API contracts.
* Removing session, model, attachment, or runtime controls.

## Technical Notes

* Located implementation in `src/aistudio_api/static/index.html`, `src/aistudio_api/static/app.js`, and `src/aistudio_api/static/style.css`.
* Applicable spec scenario: `.trellis/spec/backend/quality-guidelines.md` Static Playground Workbench UI.
* Verified with Windows pytest, browser smoke check, and WSL temporary-directory pytest.