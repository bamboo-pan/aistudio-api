# Fix Failed Login Account Record

## Goal

When a new Google account login does not actually complete, the account must not be persisted, shown in the account list as usable, activated, or selected for API calls. A failed login session should report a clear failure status so the user can retry without manually deleting a bad account.

## What I Already Know

- The user observed a new-account login failure that still created an account row with no email and marked it active.
- The saved account cannot be used for calls because the captured storage state is not an authenticated AI Studio session.
- Current browser-login flow saves the storage state after the first loose login-complete signal, even when no account identity is detected.
- `AccountStore.save_account` accepts any non-expired Google cookie state, which is valid for imports but too weak as the browser-login completion gate.
- Account rotation treats unknown-health accounts as available unless they are explicitly isolated.

## Requirements

- Browser login must require authenticated account identity evidence before saving a new account.
- If identity cannot be verified, the login session must become `failed` and no account directory, registry entry, or active-account switch may be created.
- Successful browser login must continue to save and activate accounts when an email or account identity is detected.
- Existing import/export behavior should remain unchanged; this task only tightens the browser-login flow.
- The user-facing login status response should surface a clear error when login verification fails.

## Acceptance Criteria

- [x] A browser-login session with only anonymous/non-identity Google cookies fails and does not call `save_account`.
- [x] A browser-login session that detects an email saves the account, marks the session completed, and exposes the saved account ID/email.
- [x] Unit tests cover failed identity verification and successful browser-login persistence.
- [x] Relevant account/login unit tests pass.
- [x] WSL real-environment verification is performed because this changes account/browser behavior.

## Definition of Done

- Code follows backend specs and existing account-service patterns.
- Tests added/updated for the regression.
- No unrelated behavior or metadata churn is included.
- Trellis task files are committed with the implementation.

## Out of Scope

- Changing credential import validation semantics.
- Redesigning account rotation or the account UI.
- Adding a manual cleanup flow for already-saved bad accounts.

## Technical Notes

- Primary implementation target: `src/aistudio_api/infrastructure/account/login_service.py`.
- Existing storage-state validation lives in `src/aistudio_api/infrastructure/account/account_store.py` and should remain permissive enough for imports.
- Relevant tests are under `tests/unit/test_account_auth_activation.py`, `tests/unit/test_account_credentials.py`, and `tests/unit/test_account_health_and_selection.py`.
- Verification details are recorded in `verification.md`.
