# Adjust Image Session Context Layout

## Goal

Make the image editing workflow easier to navigate by placing the current context before saved session history and moving the new-session action next to the current context, where users naturally look when managing an editing conversation.

## Requirements

* Swap the order of the image sidebar panels so the current context / editing session appears before saved session history.
* Move the `新会话` action out of the material-upload step and into the current context panel header.
* Make the new-session action visually more prominent than a small secondary button while keeping it disabled when there is no current editing context to clear.
* Preserve the existing `clearImageEditSession()` behavior and the upload-reference workflow.
* Keep the layout responsive on desktop and mobile without overlapping text or controls.

## Acceptance Criteria

* [x] In the image Studio sidebar, `上下文 / 编辑会话` renders above `会话历史 / 已保存会话`.
* [x] `新会话` is displayed near the current context header, not beside `上传参考` in the material step.
* [x] The new-session button is easier to notice through placement and styling, and remains disabled when no base image, references, or conversation exist.
* [x] Existing static frontend tests pass.
* [x] The UI is checked in a real WSL test environment as required for code/UI changes.

## Definition of Done

* Focused static frontend change only.
* Unit/static frontend tests pass.
* Real environment smoke check passes.
* Task files and implementation are committed together.

## Technical Approach

Update `src/aistudio_api/static/index.html` to reorder the sidebar panels and relocate the `clearImageEditSession()` button into the edit-session panel header. Update `src/aistudio_api/static/style.css` with a dedicated compact primary action style for the header button and responsive wrapping behavior.

## Decision (ADR-lite)

**Context**: The previous `新会话` button was grouped with reference uploads in step 2, while the action actually clears the edit conversation context.

**Decision**: Treat `新会话` as a context-management action and place it in the current context panel header.

**Consequences**: The button becomes discoverable where users inspect the active editing session. The material-upload step stays focused on adding references.

## Out of Scope

* No backend API or persistence behavior changes.
* No changes to session save/restore/delete semantics.
* No larger redesign of the image Studio workflow.

## Technical Notes

* Existing sidebar panels are in `src/aistudio_api/static/index.html` under `image-side-column`.
* Existing button behavior is `clearImageEditSession()` in `src/aistudio_api/static/app.js`.
* Static frontend capability tests already cover image sessions and `clearImageEditSession()` presence.

## Verification

* Windows: `C:/Users/bamboo/Desktop/aistudio-api_u1/.venv/Scripts/python.exe -m pytest tests/unit/test_static_frontend_capabilities.py` -> 10 passed.
* WSL real environment: `/home/bamboo/aistudio-api-ui-test/.venv/bin/python -m pytest tests/unit/test_static_frontend_capabilities.py` -> 10 passed.
* Browser smoke: WSL server at `http://127.0.0.1:8011/static/index.html#images`; verified context panel before history, new-session button inside context panel with icon, disabled initially, and absent from the upload-reference step.

## Spec Update Decision

No `.trellis/spec/` update required. The task did not introduce or change API signatures, storage contracts, environment configuration, cross-layer behavior, or reusable implementation conventions.