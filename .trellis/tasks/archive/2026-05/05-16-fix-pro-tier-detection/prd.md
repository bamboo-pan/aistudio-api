# fix: Pro account tier shows Free

## Goal

Fix the account tier detection flow so real AI Studio Pro credentials stored in WSL are detected and persisted as `pro` instead of remaining `free`, and the account management UI reflects the backend state.

## What I already know

* The user reports the real WSL credentials are Pro, but the account tier dropdown currently shows Free.
* The UI renders `tierLabel(a.tier)` from `/accounts`; it does not independently classify account tier.
* Imported single-account storage states currently default to `tier="free"` unless later refreshed.
* `/accounts/{account_id}/test` can refresh the tier only when a runtime browser session exposes `detect_tier_for_auth_file`.
* Existing tier detection scrapes only compact header/banner/nav text and only recognizes `PRO`, `AI PRO`, `ULTRA`, or `AI ULTRA` close to an email.

## Requirements

* Use the real WSL credentials path during verification without committing secrets.
* Detect Pro/Ultra from the current AI Studio page reliably enough for the real Pro account.
* Persist refreshed tier into account metadata so `/accounts`, `/accounts/active`, rotation, and UI all agree.
* Keep manual tier override behavior intact.
* Include current workspace Trellis onboarding changes in the final work as requested.

## Acceptance Criteria

* [ ] Unit tests cover the new tier parsing cases and no-regression Free behavior.
* [ ] Relevant unit tests pass locally.
* [ ] WSL real-environment test with real credentials detects `pro` for the user's account.
* [ ] No credential material is committed or printed in final output.

## Out of Scope

* Changing AI Studio credentials format.
* Reworking the full account management UI.
* Adding a new external dependency.

## Technical Notes

* Backend detection: `src/aistudio_api/infrastructure/account/tier_detector.py`.
* Account persistence: `src/aistudio_api/infrastructure/account/account_store.py` and `src/aistudio_api/application/account_service.py`.
* API route: `src/aistudio_api/api/routes_accounts.py`.
* Frontend display: `src/aistudio_api/static/app.js` and `src/aistudio_api/static/index.html`.
* Existing tests: `tests/unit/test_account_health_and_selection.py`.

## Research References

* `research/account-tier-flow.md` — local code path and likely failure points.