# Request log lifecycle management

## Goal

Make the request log page useful as an operational/debugging tool by treating one complete request lifecycle as the smallest unit. Entries that belong to the same API exchange must be grouped together, and management actions must operate on that complete request rather than on a single phase record.

## What I already know

* The user reports the current request log page mixes records together, making it hard to inspect complete request lifecycles.
* The smallest management unit should be a complete request.
* Existing request logging already stores a `chain_id` on each entry.
* Known phases include `client_request`, `upstream_request`, `upstream_response`, and `client_response`.
* Existing API routes support status, list, and single-entry detail, but do not support grouped lifecycle detail, deletion, or export.
* Existing frontend lists individual log entries and selects one `activeRequestLogId` at a time.

## Assumptions

* `chain_id` is the lifecycle grouping key for a complete request.
* A legacy entry without a usable `chain_id` should be treated as a one-entry lifecycle group keyed by its own id.
* Export should return complete JSON for selected lifecycle group(s) through the browser download flow.
* Deletion should remove every stored entry in the selected lifecycle group(s).

## Requirements

* The request log list must display lifecycle groups, not individual phase entries.
* Each group summary must show enough information to scan: primary model/title, first/last time, phase count, total size, status, elapsed time, and route/URL hint.
* Selecting a request must load all entries in that lifecycle group and display the phases together in order.
* The UI must support selecting complete request groups, including select-all for the currently loaded list.
* The UI must support deleting selected complete request groups.
* The UI must support exporting the active group and selected groups as JSON.
* Existing status toggle and refresh behavior must keep working.
* Existing single-entry detail route should keep working for compatibility unless replacing it is required.

## Acceptance Criteria

* [x] `/request-logs` returns grouped lifecycle summaries by default.
* [x] A lifecycle detail endpoint returns every entry for a `chain_id` in stable phase/time order.
* [x] Deleting a lifecycle group removes all entries in that group and leaves unrelated groups intact.
* [x] Batch deletion accepts complete request group identifiers and removes all entries for each selected lifecycle.
* [x] Exporting returns complete lifecycle JSON for the active or selected complete requests.
* [x] The request log page shows grouped list items and grouped phase details, not a flat mixed list.
* [x] UI selection, delete, and export actions operate on complete request groups.
* [x] Unit tests cover grouping, detail, delete, and export behavior.
* [x] Frontend tests or equivalent static checks cover the new grouped request management UI.
* [x] Real WSL API and frontend UI testing pass because this touches API and frontend behavior.

## Definition of Done

* Tests added/updated for backend and frontend behavior.
* Relevant lint/type/syntax checks pass.
* Real WSL API-level and frontend UI-level smoke tests pass.
* Task files, code changes, and verification notes are committed.

## Out of Scope

* Full-text search/filtering across request bodies.
* Pagination beyond the existing limit-based list behavior.
* Editing or replaying logged requests.
* Changing the low-level capture/logging points unless needed to preserve lifecycle grouping.

## Technical Notes

* Backend storage: `src/aistudio_api/infrastructure/request_logs.py`.
* Backend API: `src/aistudio_api/api/routes_request_logs.py`.
* Frontend state/actions: `src/aistudio_api/static/app.js`.
* Frontend markup/styles: `src/aistudio_api/static/index.html`, `src/aistudio_api/static/style.css`.
* Existing tests: `tests/unit/test_request_logs.py`, `tests/unit/test_static_frontend_capabilities.py`.

## Verification Notes

* Focused tests: `python -m pytest tests/unit/test_request_logs.py tests/unit/test_static_frontend_capabilities.py` -> 22 passed.
* Full unit suite: `python -m pytest tests/unit` -> 269 passed.
* Syntax: `python -m compileall -q src tests/unit` -> passed.
* Static JS syntax: `node --check src/aistudio_api/static/app.js` -> passed.
* Merge freshness: `git fetch origin` then `git merge --ff-only origin/master` -> already up to date.
* WSL real API: temporary copy under `/home/bamboo/aistudio-api-realtest-request-log-lifecycle-current`, real accounts copied from `/home/bamboo/aistudio-api/data/accounts`, enabled request logging, sent browser-backed `/v1/chat/completions` with `gemini-3.1-flash-lite`, and verified grouped list/detail/export contained `client_request`, `upstream_request`, `upstream_response`, and `client_response` sharing one `chain_id`.
* WSL real UI: opened `http://127.0.0.1:18116/static/index.html?ui-fix=1#requests`, verified grouped request rows and lifecycle phase detail, selected one complete four-phase request, exported it through the UI success path, deleted the selected group, and observed counts change from 4 groups / 12 entries to 3 groups / 8 entries with no selection left.
* Responsive UI smoke: request page controls remained visible with no horizontal overflow in the integrated browser viewport check.