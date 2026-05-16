# Improve Frontend Dynamic Layout

## Goal

Reduce wasted blank space in the static web UI and make the image generation and account management pages adapt to wider desktop viewports while preserving the existing compact mobile behavior.

## What I Already Know

* User screenshots show large unused blank regions on the left/right of the image generation and account management pages.
* The current layout centers page content with fixed max widths: generic `.page-pad`, `.image-studio-pad`, and `.account-pad` constrain wide viewports.
* The image generation page already has a workbench grid, but the outer container prevents it from using available width.
* The account page has dense dashboard/table content that benefits from a wider working area.

## Assumptions

* This should be a UI layout improvement only; no API behavior should change.
* Desktop and wide desktop should use more horizontal space, but content should still retain readable padding and not stretch edge-to-edge.
* Mobile and tablet should remain single-column where the existing media queries already apply.

## Requirements

* Let image generation and account management pages expand dynamically with the viewport instead of staying locked to narrow fixed max widths.
* Keep the main form/results/history areas organized and avoid horizontal overflow.
* On image generation, make wide screens useful by allowing result/history panels to gain columns and image previews to scale up sensibly.
* On account management, make dashboard cards and tables use more of the available content width.
* Preserve existing visual style, controls, and Alpine state behavior.

## Acceptance Criteria

* [x] At desktop widths, image and account pages no longer show large outer blank columns caused by fixed max-width containers.
* [x] At wide desktop widths, the image results/history grids can use additional columns and larger media areas.
* [x] At tablet/mobile widths, the pages continue to collapse to the existing single-column layouts.
* [x] Static frontend regression tests pass.
* [x] Real environment smoke test is run for the web UI.

## Definition Of Done

* Tests added or updated where appropriate.
* Relevant unit/static tests pass.
* WSL real-environment smoke test passes for the changed frontend.
* Task files are committed with the implementation.

## Out Of Scope

* Changing API request or account rotation behavior.
* Redesigning the whole visual language.
* Adding new frontend dependencies.

## Technical Notes

* Main target files: `src/aistudio_api/static/style.css`, possibly static frontend tests.
* Relevant existing tests: `tests/unit/test_static_frontend_capabilities.py`.
* Relevant spec context: `.trellis/spec/backend/index.md`, `.trellis/spec/backend/quality-guidelines.md`, `.trellis/spec/guides/index.md`.