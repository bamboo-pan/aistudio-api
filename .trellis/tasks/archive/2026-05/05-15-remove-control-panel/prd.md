# Remove redundant control panel

## Goal

Determine whether the standalone control panel is redundant with account management and remove it only if doing so does not hide unique operational data.

## What I already know

* The user asked whether the control panel features are already included in account management, and if so to delete the control panel.
* The static frontend has separate `dashboard` and `accounts` views.
* Account management already covers active account, account count, health/cooling state, Pro/Ultra count, per-account requests/success/429, rotation mode/configuration, force switch, login/import/export, and image usage by resolution.
* The control panel uniquely displays model-level `/stats` data: requests, success, 429, errors, last used, and overall model totals.

## Requirements

* Move model-level statistics into account management before deleting the control panel route and navigation item.
* Keep account management as the single operational/account page, covering active account, rotation/account health, account-level usage, image resolution usage, and model-level runtime statistics.
* Delete the standalone control panel UI and its frontend state/routing entry points once the model statistics are visible from account management.
* Keep backend `/stats` available because the migrated account management model statistics still need it.

## Acceptance Criteria

* [ ] The sidebar no longer shows a separate 控制面板 item.
* [ ] `#dashboard` is no longer a supported frontend route; old dashboard hashes land on an existing page.
* [ ] No unused dashboard-only frontend state/getters/loaders remain unless model stats are migrated elsewhere.
* [ ] Static frontend tests reflect the selected behavior.
* [ ] Project tests pass for the touched area.

## Definition of Done

* Tests added or updated where appropriate.
* Lint/typecheck or targeted tests pass.
* Trellis spec-update gate reviewed.
* Changes are committed through the Trellis finish flow when approved.

## Technical Approach

Move the compact model stats cards/table from the dashboard page into account management, then remove the dashboard navigation item, page block, hash route, and dashboard-only navigation logic. Keep `/stats` loading because account management will use it.

## Decision (ADR-lite)

**Context**: Account management covers account and rotation operations, but the control panel contains model-level runtime counters sourced from `/stats` and `RuntimeState.model_stats`.

**Decision**: Migrate model-level statistics into account management, then delete the standalone control panel.

**Consequences**: The UI keeps the existing model-level visibility while simplifying navigation to a single account/operations page.

## Out of Scope

* Removing backend `/stats` unless separately requested.
* Redesigning the account management page beyond what is needed to preserve or remove dashboard information.

## Technical Notes

* `src/aistudio_api/static/index.html` contains the dashboard nav item and dashboard page.
* `src/aistudio_api/static/app.js` supports `dashboard`, `loadStats`, `stats`, `statsTotals`, `totalReqs`, and `totalRL`.
* `src/aistudio_api/application/api_service.py` returns model-level stats from `stats_response()`.
* `src/aistudio_api/api/state.py` records model-level stats in `RuntimeState.model_stats`.
