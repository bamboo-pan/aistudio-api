# Image Generation Aspect Ratio Preview

## Goal

Improve the image generation page so generated images and history thumbnails keep their real visual proportions instead of being forced into square cropped tiles, and let users click an image to view the complete original image in a preview overlay.

## What I Already Know

* The user reported that image generation page thumbnails look strange when their aspect ratio is not preserved.
* Existing result and history cards in `src/aistudio_api/static/index.html` render images directly inside `.image-card`.
* Existing CSS forces image cards to `aspect-ratio:1/1` with `object-fit:cover`, which crops non-square images and makes wide/tall outputs look wrong.
* The static frontend uses Alpine state in `src/aistudio_api/static/app.js`; image items are already normalized through `imageUrl(item)` and `lightweightImageItem(item)`.
* Static frontend behavior is covered by string-based tests in `tests/unit/test_static_frontend_capabilities.py`.

## Requirements

* Image result cards must preserve the image's real aspect ratio when displayed as thumbnails.
* Local history cards must preserve the image's real aspect ratio when displayed as thumbnails.
* Thumbnails may appear smaller inside their tile if needed, but they must not crop or stretch the source image.
* Clicking a result or history image must open a preview overlay.
* The preview overlay must show the full image using the real image proportions, constrained to the viewport so the complete image remains visible.
* The preview must close when the user clicks the preview image/backdrop again or uses the close button.
* The preview should also close via Escape for normal modal behavior.
* Existing image actions such as download, set as base image, use as reference, retry, selection, and delete must continue to work.

## Acceptance Criteria

* [ ] Generated result images no longer use square cropped `object-fit: cover` card rendering.
* [ ] History images no longer use square cropped `object-fit: cover` card rendering.
* [ ] A thumbnail for a non-square image displays fully with correct proportions, even if empty space appears around it.
* [ ] Clicking a result image opens a large preview of that same image.
* [ ] Clicking a history image opens a large preview of that same image.
* [ ] The preview image uses contain-style sizing and never exceeds the viewport.
* [ ] Clicking the backdrop, clicking the preview image, pressing Escape, or clicking the close button closes the preview.
* [ ] Existing static frontend unit tests pass, with coverage updated for the preview behavior.
* [ ] Real WSL environment test passes before finish work.

## Definition of Done

* Tests added or updated for the static frontend behavior.
* Lint/type-check/test commands relevant to the changed files pass locally.
* Real WSL test is run according to `AGENTS.md`.
* Trellis check and spec-update gates are completed before committing.
* Commit includes the Trellis task record.

## Technical Approach

Use existing Alpine state rather than adding new frontend dependencies. Wrap card images in a fixed thumbnail stage/button that uses `object-fit: contain` so thumbnails keep proportions. Add lightweight preview state and methods in `app.js`, render one global preview overlay in `index.html`, and style it in `style.css` as a viewport-constrained modal.

## Decision (ADR-lite)

**Context**: Existing card images are visually consistent in size but force every image into a square cover crop, which is poor for generated images with varied aspect ratios.

**Decision**: Keep stable card tile sizing but make the image itself `contain` inside the tile, then provide a modal overlay for full-size inspection.

**Consequences**: Some thumbnails will have letterboxing/empty space, but image proportions remain correct and users can inspect the complete image on click.

## Out of Scope

* Changing backend image generation APIs or storage behavior.
* Adding zoom, pan, carousel navigation, or keyboard previous/next controls.
* Redesigning the entire image generation page layout.
* Changing chat page image attachment thumbnails.

## Technical Notes

* Main files expected to change: static frontend HTML/CSS/JS plus static frontend unit tests.
* No external technical research is needed; this is a small UI behavior change using existing browser and Alpine capabilities.