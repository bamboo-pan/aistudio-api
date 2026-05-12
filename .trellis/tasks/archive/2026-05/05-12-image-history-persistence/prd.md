# Persist Generated Images and Manage History

## Goal

Generated images from the web UI should survive page refreshes and be easy to trace later. Instead of storing large base64/data URL payloads in browser `localStorage`, the backend should persist generated image files under a static directory and return stable file URLs that the frontend can keep in its local history.

## What I Already Know

* The current frontend image page stores `imageHistory` in `localStorage` under `aistudio.imageHistory`.
* The current `/v1/images/generations` response can return `url`, but that URL is a `data:image/...;base64,...` value rather than a server-hosted file URL.
* Large base64 histories can exceed browser `localStorage` quota, so images visible before refresh may disappear after refresh because the save silently fails.
* The FastAPI app currently mounts package static assets at `/static` from `src/aistudio_api/static`.
* The image page already has result/history galleries, download buttons, retry buttons, and a clear-history button.

## Requirements

* Persist images generated through the web/API image generation path to a backend-owned static files directory.
* Return each generated image with a stable server file URL while preserving OpenAI-compatible image response behavior as much as practical.
* Store only lightweight metadata in frontend local history: file URL, prompt, model, size, index, created time, and any useful identifier/path needed for management.
* Refreshing the frontend should keep generated image history visible as long as the backend file still exists.
* Add common local history management controls:
  * select individual history items
  * select all / clear selection
  * batch download selected images
  * delete selected history entries and their corresponding backend files when possible
  * keep single-item download, retry, and delete actions ergonomic
* Failed backend deletion should not corrupt frontend history; the UI should surface a clear error and keep enough state for retry.
* Generated images should be retained indefinitely by default and only deleted when the user explicitly deletes them.
* Keep the image generation UI consistent with the existing Alpine/static frontend style.

## Acceptance Criteria

* [ ] A generated image is written to a configurable/static backend directory with a stable URL.
* [ ] `/v1/images/generations` responses for `response_format=url` contain server file URLs instead of large data URLs for persisted images.
* [ ] Frontend history survives a browser refresh without storing full base64 image payloads in `localStorage`.
* [ ] Users can select multiple local history images and download them.
* [ ] Users can delete selected local history images, and the backend files are removed when they are server-hosted generated images.
* [ ] Users can delete a single local history image from its card.
* [ ] Backend-stored generated images are not auto-pruned by default.
* [ ] Empty, selected, busy, success, and error states are handled without layout breakage.
* [ ] Existing OpenAI-compatible clients that request image data still receive usable image content.
* [ ] Focused unit tests cover backend persistence/response behavior and frontend static behavior where the project already has tests.

## Definition of Done

* Tests added or updated for backend file persistence and frontend history controls where appropriate.
* Existing unit tests pass for affected areas.
* Static file serving works from a fresh server start.
* No generated binary image artifacts are committed to git.
* Documentation or configuration notes are updated if a new environment variable or storage path is introduced.

## Technical Approach

Recommended approach: persist generated images under a runtime data directory outside the packaged frontend assets, mount it with FastAPI as a static route such as `/generated-images`, and include file metadata in the image API response. The frontend stores server URLs and metadata in local history, uses the browser for single downloads, performs batch downloads by triggering each selected URL, and calls a backend deletion endpoint for server-hosted generated images before removing them from history.

Likely implementation details:

* Add settings for generated image storage directory and public route, defaulting to a project-local/runtime data path rather than `src/aistudio_api/static`.
* Add an application/infrastructure helper to write image bytes with safe generated filenames and return URL/path metadata.
* Mount the generated image directory in the FastAPI app.
* Extend image response item metadata with enough information for frontend management while retaining `b64_json` fallback when compatibility requires it.
* Add a small deletion API scoped to generated image files only, with path traversal protection.
* Update the frontend image page state with selected history IDs and management methods.
* Add CSS for selection checkboxes/selected cards/batch toolbar in the existing visual style.

## Decision (ADR-lite)

**Context**: Browser `localStorage` is not reliable for large generated-image base64 payloads, and generated images need to be traceable after refresh.

**Decision**: Store image files on the backend and keep frontend history lightweight by storing file URLs and metadata.

**Consequences**: Refresh survival improves and local history becomes manageable, but the backend now owns generated-image lifecycle and needs deletion safeguards. Generated files may consume disk over time, so the UI must make manual deletion straightforward.

## Open Questions

* None.

## Out of Scope

* Cloud/object storage integration.
* Multi-user authentication or per-user private galleries beyond the existing local app assumptions.
* Editing previously generated images.
* Compressing or transcoding generated images beyond preserving the generated mime type.

## Technical Notes

* Current app static mount: `src/aistudio_api/api/app.py` mounts `/static` to packaged frontend files.
* Current image API response assembly: `src/aistudio_api/application/api_service.py` builds image items from generated bytes.
* Current frontend history logic: `src/aistudio_api/static/app.js` saves `imageHistory` directly to `localStorage`.
* Current image UI: `src/aistudio_api/static/index.html` has result and local-history galleries.
* Current image CSS: `src/aistudio_api/static/style.css` has `.image-gallery`, `.image-card`, and related controls.