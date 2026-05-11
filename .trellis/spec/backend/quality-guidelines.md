# Quality Guidelines

> Code quality standards for backend development.

---

## Overview

This single-repo project includes a small static Alpine.js control panel under
`src/aistudio_api/static/`. Frontend code should stay lightweight and reuse the
existing API helpers/state patterns instead of introducing a build step for small
dashboard changes.

---

## Scenario: Static Account UI Consumes Optional Account APIs

### 1. Scope / Trigger

- Trigger: Frontend account-management UI reads account list, active account,
	login status, and rotation data from backend APIs.
- Applies when a page combines a required collection endpoint with an optional
	singleton endpoint, such as `/accounts` plus `/accounts/active`.

### 2. Signatures

- `GET /accounts` -> list of accounts.
- `GET /accounts/active` -> active account or `404` when no active account exists.
- `POST /accounts/login/start` -> `{ "session_id": string }`.
- `GET /accounts/login/status/{session_id}` -> login status payload.
- `POST /accounts/{account_id}/activate` -> activated account.
- `PUT /accounts/{account_id}` with `{ "name": string }` -> updated account.
- `DELETE /accounts/{account_id}` -> `{ "ok": true }`.

### 3. Contracts

- Account rows use `id`, `name`, `email`, `created_at`, and `last_used` from
	`/accounts` as the source of truth for display identity.
- Rotation stats may be merged into rows, but must not overwrite fresher account
	identity fields from `/accounts`.
- `404` from `/accounts/active` means "no active account" and is not a fatal
	page-load error.

### 4. Validation & Error Matrix

- `/accounts` fails -> show an account-list error/empty state; do not show stale
	success data as if it were current.
- `/accounts/active` returns `404` -> clear active account state and keep the
	account list visible.
- Login start succeeds without `session_id` -> surface a failed login state.
- Delete, rename, activate, or rotation update fails -> keep current state and
	show a user-visible error.

### 5. Good/Base/Bad Cases

- Good: Load `/accounts` and `/accounts/active` independently so active-account
	absence does not hide existing accounts.
- Base: Refresh accounts, active account, and rotation data after account-mutating
	operations.
- Bad: Put `/accounts` and `/accounts/active` in one `Promise.all` where a `404`
	from active account rejects the whole refresh.

### 6. Tests Required

- JavaScript syntax check for edited static scripts, for example
	`node --check src/aistudio_api/static/app.js`.
- Smoke test account refresh with `/accounts/active` returning `404` while
	`/accounts` returns rows.
- Smoke test failed login-start responses and duplicate-submit guards for account
	operations.

### 7. Wrong vs Correct

#### Wrong

```javascript
const [accounts, active] = await Promise.all([
	fetch('/accounts').then(r => r.json()),
	fetch('/accounts/active').then(r => r.json()),
]);
```

#### Correct

```javascript
const accounts = await fetchJson('/accounts');
let active = null;
try {
	active = await fetchJson('/accounts/active');
} catch (error) {
	if (error.status !== 404) throw error;
}
```

---

## Forbidden Patterns

- Do not let optional singleton API failures such as `/accounts/active` reject a
	whole page refresh that also includes required collection data.

---

## Required Patterns

- Account-management UI actions that mutate state must refresh the account list,
	active account state, and rotation stats after success.
- Buttons that start account mutations must guard against duplicate submits while
	the request is in flight.

---

## Testing Requirements

- For static JavaScript changes, run a syntax check with `node --check` when Node
	is available.
- Run the closest practical project checks and record any unrelated failures.

---

## Code Review Checklist

- Does the UI handle empty account lists and missing active accounts separately?
- Do account mutations refresh every dependent view model?
- Are request-in-flight states disabling repeat clicks for destructive or
	mutating actions?
