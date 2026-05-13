# Improve Image Page Scrolling Layout

## Goal

Fix the image generation page interaction regression where the left generation/edit form remains sticky while scrolling and blocks content behind it. The page should scroll naturally without any panel obscuring results, edit conversation, or history cards.

## Requirements

* Remove or replace the sticky behavior from the image form panel so it never floats over later content during page scroll.
* Keep the image creation/edit controls visible in a clear first section, but let them participate in normal document flow.
* Preserve the existing image editing features: upload references, base image, edit session, results, and local history actions.
* Improve the page layout so results, edit conversation, and local history are easy to scan after scrolling.
* Maintain responsive behavior on mobile and desktop.

## Acceptance Criteria

* [ ] Scrolling the image page does not cause the form panel to overlay or block history/results/session content.
* [ ] The form panel uses normal flow layout on desktop and mobile.
* [ ] Results, edit session, and local history remain visible and accessible.
* [ ] Existing static frontend tests pass and cover the non-sticky layout.
* [ ] Full test suite passes on Windows and WSL real test copy.

## Definition of Done

* CSS/HTML changes are minimal and scoped to the image page layout.
* Tests updated for the layout contract.
* Windows and WSL test runs pass.

## Technical Notes

* Root cause: `.image-form-panel{position:sticky;top:20px;z-index:5}` keeps the form floating while the `.scroll-area` scrolls, so it covers content behind it.
* Likely files: `src/aistudio_api/static/style.css`, `tests/unit/test_static_frontend_capabilities.py`.

## Out of Scope

* Changing backend image editing behavior.
* Redesigning all app navigation or account/dashboard pages.
