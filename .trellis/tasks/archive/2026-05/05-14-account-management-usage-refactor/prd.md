# Refactor Account Management Page and Usage Modes

## Goal

Improve the account management experience so operators can clearly see account health, tier, rotation behavior, and image usage. Add an exhaustion rotation mode that keeps using the current account until quota/rate-limit exhaustion before switching, record image generation usage by requested resolution, and fix Pro/Ultra account tier detection so premium accounts are not shown as Free.

## What I Already Know

* The account management UI lives in `src/aistudio_api/static/index.html`, `src/aistudio_api/static/app.js`, and `src/aistudio_api/static/style.css` using Alpine state and server JSON endpoints.
* Current rotation modes are `round_robin`, `lru`, and `least_rl` in `src/aistudio_api/application/account_rotator.py`.
* `/rotation` and `/rotation/mode` expose mode, cooldown, and account stats from `src/aistudio_api/api/routes_system.py`.
* Current per-account stats track requests, success, rate-limited, errors, last use, and cooldown, but not image resolution usage.
* Current model stats in `src/aistudio_api/api/state.py` track model totals only; image generation calls go through `handle_image_generation` in `src/aistudio_api/application/api_service.py`.
* Account tier is stored in `AccountMeta.tier`, defaults to `free`, and can be manually edited through `/accounts/{id}`.
* `src/aistudio_api/infrastructure/account/tier_detector.py` already contains browser-based tier detection for Free/Pro/Ultra, but account health checks currently use only local storage-state validation and do not update tier from that detector.
* The current screenshot shows the tier dropdown rendering a Free value for an account the user says is currently Pro.

## Requirements

* Add a new rotation mode named `exhaustion` with user-facing label `耗尽模式`.
* In exhaustion mode, automatic account selection should continue using the current active account while it is healthy and suitable for the requested model.
* Exhaustion mode should switch to another suitable available account only when the current account is unavailable, isolated, missing/expired, rate-limited, or not suitable for the requested model tier preference.
* Existing manual `强制切换` behavior should still force a switch to another available account.
* Rotation mode validation, environment configuration comments, API error text, UI dropdowns, and tests must include the new mode.
* Image generation success statistics must record requested image resolution counts, such as `1024x1024`, separately from text/chat request statistics.
* Resolution usage must be exposed in `/stats` and `/rotation`/account stats where appropriate so the UI can show image usage by resolution.
* The account management page should be refactored into a cleaner, denser operational layout: quick status summary, rotation controls, account pool, per-account image-resolution usage, and credential import/export without excessive visual clutter.
* The account tier display must support correcting a Pro account shown as Free by running a tier-aware check from the UI.
* Health/tier check responses should remain sanitized and must not expose cookies or credential JSON.
* Existing account operations must continue to work: login, activate, force next, rename, delete, import, export, manual tier update, and health check.

## Acceptance Criteria

* [x] `exhaustion` is accepted by the rotation API and selectable from the account management UI.
* [x] In exhaustion mode, repeated automatic selections keep the same active healthy/suitable account until it is rate-limited or otherwise unavailable.
* [x] When the active account is rate-limited in exhaustion mode, the next request can switch to the next suitable available account.
* [x] Manual force-next still changes accounts even when exhaustion mode would otherwise keep the current account.
* [x] Successful image generation increments usage counters for the requested resolution.
* [x] `/stats` exposes resolution-level image usage in a backward-compatible way.
* [x] Account rotation stats expose per-account image resolution usage when the rotator has account context.
* [x] Account page shows per-account total image usage and a compact resolution breakdown.
* [x] Running an account check can update `tier` to `pro` or `ultra` when the detector identifies the subscription badge.
* [x] Unit tests cover exhaustion selection, image resolution statistics, tier-aware account check behavior, and static frontend affordances.
* [x] Real WSL test with the user's account directory passes the relevant service/API checks.

## Validation Results

* Local unit tests: `172 passed in 1.53s` using the workspace venv.
* UI preview: account management page rendered the new layout, `耗尽模式`, and image-resolution usage panel at `http://127.0.0.1:18080/#accounts`.
* WSL validation: `/home/bamboo/aistudio-api-u1-test` ran `172 passed in 0.96s`.
* WSL real accounts smoke: `/home/bamboo/aistudio-api/data/accounts` loaded 1 account and returned `{"account_count": 1, "has_image_sizes": true, "mode": "exhaustion", "stats_count": 1}`.

## Definition of Done

* Tests added or updated for the changed backend behavior and frontend static expectations.
* Lint/type/syntax checks pass for touched Python and static files where available.
* Real WSL validation is run against a temporary copy using the WSL account credential path described in `AGENTS.md`.
* Trellis check and spec-update gates are completed before committing.
* Work commit includes the Trellis task record, then finish/archive bookkeeping is committed and pushed according to `develop_workflow.txt`.

## Technical Approach

Implement a focused backend and frontend refactor without changing the public shape of existing fields.

* Extend `RotationMode` with `EXHAUSTION = "exhaustion"`.
* Add a helper that can prefer the active account in exhaustion mode when it passes availability and model-suitability checks.
* Preserve existing round-robin/LRU/least-rate-limited behavior for their modes.
* Add optional image metadata to account stat recording, likely through `record_success(account_id, image_size=None)` or a narrowly named companion method, and include an `image_sizes` dictionary in account stat output.
* Extend `RuntimeState.record` with optional metadata or a small image-specific recorder so model stats can keep `image_sizes` totals while existing totals remain compatible.
* Update `handle_image_generation` to pass the planned/requested size into model and account stats only after successful generation.
* Add a tier-aware account check path that uses the existing `tier_detector` when browser/Camoufox context is available, falls back to the current local health check when detection fails, and keeps sanitized API output.
* Refactor the account page toward an operations dashboard: summary strip, mode segmented/select control, account cards/table with direct actions, and compact usage chips.

## Decision (ADR-lite)

**Context**: The user needs quota-draining behavior, accurate premium tier display, and more useful image usage visibility from the account management page.

**Decision**: Add exhaustion mode as a fourth rotator strategy rather than replacing round-robin. Track image resolution counts in existing in-memory stats structures to keep persistence and storage behavior unchanged for this task. Reuse the existing tier detector instead of adding a new detection mechanism.

**Consequences**: The change remains backward-compatible and low-risk, but image usage counters stay process-memory scoped like current stats. Tier detection depends on the availability of the running browser/Camoufox environment and should degrade gracefully.

## Out of Scope

* Persisting statistics across server restarts.
* Adding a database or long-term analytics store.
* Implementing per-day/per-month quota reset tracking.
* Changing the generated image storage format.
* Replacing Alpine or splitting the frontend into a build pipeline.
* Full redesign of the chat or image generation pages beyond account-management-related navigation/status consistency.

## Technical Notes

* Relevant files inspected: `src/aistudio_api/application/account_rotator.py`, `src/aistudio_api/api/routes_system.py`, `src/aistudio_api/application/api_service.py`, `src/aistudio_api/api/state.py`, `src/aistudio_api/application/account_service.py`, `src/aistudio_api/infrastructure/account/account_store.py`, `src/aistudio_api/infrastructure/account/tier_detector.py`, `src/aistudio_api/static/index.html`, `src/aistudio_api/static/app.js`, `src/aistudio_api/static/style.css`, `tests/unit/test_account_health_and_selection.py`.
* Existing route-level tier updates are manual through `PUT /accounts/{account_id}`; the new check should not remove manual override capability.
* Current health check is deliberately credential-sanitized; tests should continue asserting credentials are not leaked.
