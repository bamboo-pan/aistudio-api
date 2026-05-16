# Account Tier Flow Research

## Current Flow

* The account table calls `accountRows`, which merges `/accounts` records with `/rotation` stats. The tier dropdown uses `tierLabel(a.tier)`.
* `/accounts` maps `AccountMeta.tier` directly through `routes_accounts._to_account_response`.
* Single-account credential import validates storage state and calls `save_account(..., tier="free")` implicitly.
* Backup import preserves `meta.tier` from the backup manifest.
* Health check can refresh tier via `AccountService.test_account_with_tier`, but only if the runtime browser session exists and can run `detect_tier_for_auth_file`.
* `tier_detector.TIER_DETECT_JS` currently limits source text to `header`, `[role="banner"]`, and `nav`; it searches for an email and then only checks the nearby lines for exact Pro/Ultra labels.

## Likely Failure Modes

* Credentials imported from a plain Playwright storage state remain Free until an explicit tier-aware health check succeeds.
* The live AI Studio UI may expose membership text outside the queried header/nav nodes, or as `Google AI Pro` / `Pro plan` / account menu text rather than exact `PRO` near the email.
* If a runtime browser session is not started, `/accounts/{id}/test` reports storage-state health but cannot refresh tier.

## Real-Environment Findings

* WSL real credentials live under `/home/bamboo/aistudio-api/data/accounts`; the test used the path through `AISTUDIO_ACCOUNTS_DIR` and did not print credential contents.
* Current AI Studio can show the tier as `PRO` appended to the email account button (`<email> PRO`) and inside the account menu with `Manage membership`.
* The original detector can fail before parsing because `BrowserSession.detect_tier_for_auth_file()` first preheated the active browser context. In a temporary environment with no active auth configured, that redirected to Google sign-in before the explicit auth file was tested.
* Direct page detection also needs to wait for `document.body.innerText`; otherwise `document.body` can briefly be null immediately after navigation.

## Verification

* Focused Windows tests: `pytest tests/unit/test_tier_detector.py tests/unit/test_gateway_session_readiness.py tests/unit/test_account_health_and_selection.py` -> passed.
* Full Windows unit tests after merging latest `origin/master`: `pytest tests/unit` -> 195 passed.
* WSL focused tests in `/home/bamboo/aistudio-api-u3-tier-test`, including the merged Camoufox launcher regression -> 35 passed.
* WSL real credential test after merge returned `tier='pro'` and `is_premium=True` for account index 1.

## Implementation Constraints

* Do not expose cookies or account data in logs or final output.
* Keep the stored tier normalized to `free`, `pro`, or `ultra`.
* Tests should focus on deterministic parsing logic rather than depending on live AI Studio DOM.