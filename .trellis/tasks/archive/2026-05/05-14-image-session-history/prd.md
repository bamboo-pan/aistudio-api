# Image Generation Session History

## Goal

Improve the image generation page so starting a new image conversation clears the current prompt and output state, and users can find previous image conversations from a backend-persistent session history list and continue editing them.

## What I Already Know

* The user reports that after image generation, the description field should be cleared and wait for the next instruction.
* Clicking `新会话` should clear previous text and outputs so the page is ready for a new conversation.
* The page should provide session history so previous image conversations can be found and continued.
* The existing frontend is a static Alpine app in `src/aistudio_api/static/app.js`, `index.html`, and `style.css`.
* The current page already has `imagePrompt`, `imageResults`, `imageHistory`, `imageBaseImage`, `imageReferences`, and `imageConversation` state.
* Existing `imageHistory` stores individual images in `localStorage` under `aistudio.imageHistory`; it does not restore a full conversation draft/output/context and is not shared across browsers.
* Existing `clearImageEditSession()` only clears image references, base image, conversation log, and reference error; it does not clear prompt text or current output.
* The backend already persists generated image files under `settings.generated_images_dir` and exposes generated-image deletion through a small route module.

## Assumptions

* Session history must be stored on the backend so it survives browser reloads and can be shared by clients using the same server data directory.
* Backend persistence can use JSON files under the runtime data directory for this task; no external database is required.
* A restored session should bring back enough state to continue editing: prompt, current results, base image, references, conversation log, model, size, count, and last request when available.
* The existing per-image local history/material library remains available and should not be removed.

## Requirements

* After a successful image generation or image edit, clear the description textarea so it is empty and ready for the next instruction.
* Preserve the just-submitted prompt in the current output card metadata and conversation log even after the input clears.
* `新会话` must clear the prompt, current output, error state, base image, reference images, conversation log, last request, and transient selection/preview state needed for a clean new conversation.
* `新会话` must not erase saved historical sessions or the existing local image material history.
* Add a visible session history area to the image generation page.
* Add backend API support to create/update, list, retrieve, and delete image sessions.
* Each saved session entry should show a recognizable title/summary, timestamp, model/size metadata, turn count, and a small preview image when available.
* Users must be able to restore a saved session from the history list and continue editing from that session.
* Users must be able to delete a saved session from the history list.
* Persist session snapshots after successful generation/edit, and refresh the session history list from the backend.
* Session deletion must delete only the session record, not generated image files or existing image material history.
* Maintain responsive layout on desktop and mobile.

## Acceptance Criteria

* [ ] Generate an image from a prompt; when the request succeeds, the textarea becomes empty while generated output still displays its original prompt.
* [ ] Click `新会话` after generated output exists; the textarea, output area, editing context, references, and conversation log are cleared.
* [ ] Existing local image history remains available after `新会话`.
* [ ] A session appears in backend-backed session history after a successful generation/edit.
* [ ] Reload the browser or open another browser session against the same server; saved sessions can still be listed and restored.
* [ ] Restoring a session repopulates the conversation log, current output, model/size/count, base image/references where applicable, and allows another edit to be sent.
* [ ] Deleting one session history item removes only that saved session and does not delete generated image files or the material library.
* [ ] Unit tests cover the backend image session store/routes.
* [ ] Static frontend tests cover the new state names, controls, and API calls.
* [ ] Real WSL environment test passes per project workflow.

## Technical Approach

* Add a backend image-session persistence component that stores lightweight session snapshots in JSON under the runtime data directory.
* Add API routes for listing, retrieving, upserting, and deleting image sessions.
* Keep generated image files and existing image material history separate from conversation session records.
* Update the image generation frontend to load session history from the backend, save/update the active session after successful generations, restore selected sessions, and clear current state on `新会话`.
* Keep the current individual-image local history behavior for quick material reuse unless a future task migrates it to the backend.

## Decision (ADR-lite)

**Context**: The user needs previous image conversations to be recoverable and editable beyond the current page state. Browser-local storage would match the old material history, but it would not satisfy cross-browser/server-persistent recovery.

**Decision**: Use backend-persistent image session history for this task, backed by local JSON storage under the server runtime data directory.

**Consequences**: This keeps deployment simple and avoids adding a database while making sessions durable for clients sharing the same server. It is not account-scoped yet, so multi-user permissions and remote sync remain future work.

## Definition of Done

* Tests added or updated for the static frontend behavior surface.
* Lint/typecheck/test command relevant to the touched code is green.
* Real WSL test run is completed.
* Trellis task records are included in the final commit.
* Behavior remains consistent with existing image generation page style and local history conventions.

## Out of Scope

* Account-scoped auth or permissions for history records.
* Changing the image generation API request/response contract.
* Reworking the whole image generation layout beyond what is needed for session history.
* Deleting generated image files when deleting a saved session.

## Technical Notes

* Impacted files are expected to include `src/aistudio_api/static/app.js`, `src/aistudio_api/static/index.html`, `src/aistudio_api/static/style.css`, backend route/store files, and related unit tests.
* Likely backend storage: a new image-session JSON store under the runtime data directory, separate from generated image files.
* The session data should use lightweight image items rather than storing base64 payloads, following existing `lightweightImageItem()` behavior.
* The current `imageConversation` already records user prompt turns and assistant image turns and can be persisted inside session snapshots.
* The frontend should continue using the existing individual-image local history for material-library behavior while relying on backend APIs for conversation session history.
