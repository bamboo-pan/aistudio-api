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

---

## Scenario: Browser Hook Page Readiness

### 1. Scope / Trigger

- Trigger: Gateway code installs browser hooks for AI Studio request capture or
	replay.
- Applies when code depends on page-global AI Studio runtime objects such as
	`window.default_MakerSuite`, `window.__bg_service`, or a detected snapshot
	function.

### 2. Signatures

- `BrowserSession._ensure_hook_page_sync() -> Page`: returns a page that is ready
	for hook installation.
- `BrowserSession._goto_aistudio_sync(page) -> None`: navigates to a chat route
	and waits for chat runtime readiness.
- `BrowserSession._install_hooks_sync(page) -> None`: installs hooks only after
	the page readiness contract is satisfied.

### 3. Contracts

- Chat page readiness means all of the following are true:
	- The current URL is an AI Studio chat route, not merely any
		`aistudio.google.com` page.
	- `window.default_MakerSuite` is available in the main world.
	- A chat `textarea` is present for BotGuard service priming.
- Reused browser pages must be normalized back to the chat route before hook
	installation when login, account, settings, or other AI Studio routes are
	active.
- Hook-install errors should include URL/title/readiness details when the chat
	runtime never becomes available.

### 4. Validation & Error Matrix

- Page on non-AI-Studio URL -> navigate to the new-chat URL, then fallback chat
	URL if needed.
- Page on AI Studio but not a chat route -> navigate to a chat route before
	installing hooks.
- Chat route missing `default_MakerSuite` or textarea after readiness timeout ->
	raise a diagnostic error with URL, title, route/readiness flags, and body text
	context.
- Hook script returns `already_hooked` -> reuse existing hooks without changing
	the page.
- Hook script returns `hooked:<snapKey>` -> store the snapshot key and continue.

### 5. Good/Base/Bad Cases

- Good: A freshly logged-in account lands on an AI Studio account/home route;
	the session navigates to new chat, waits for runtime + textarea, then installs
	hooks.
- Base: A ready chat page with existing hooks returns `already_hooked` and is
	reused.
- Bad: Treat any `aistudio.google.com` URL as hook-ready and call the hook script
	on a route where `window.default_MakerSuite` does not exist.

### 6. Tests Required

- Unit-test route gating: non-chat AI Studio URLs must trigger navigation before
	hook installation.
- Unit-test ready-page reuse: a chat route with runtime + textarea should not be
	navigated unnecessarily.
- Unit-test diagnostics: readiness failures should include enough page state to
	debug login/runtime issues.
- Run a syntax check over changed Python files, for example `python -m compileall
	src tests`.

### 7. Wrong vs Correct

#### Wrong

```python
if "aistudio.google.com" not in (page.url or ""):
    self._goto_aistudio_sync(page)
self._install_hooks_sync(page)
```

#### Correct

```python
if not self._is_chat_page_ready_sync(page):
    self._goto_aistudio_sync(page)
self._install_hooks_sync(page)
```

---

## Scenario: Active Account Auth Handoff For Browser Sessions

### 1. Scope / Trigger

- Trigger: Account login, account activation, API startup warmup, or gateway
	browser session creation uses saved Google auth state.
- Applies when browser code depends on account cookies from the account store to
	open AI Studio without reaching Google sign-in.

### 2. Signatures

- `AccountStore.save_account(...) -> AccountMeta`: persists account storage state
	and should make a newly logged-in account active.
- `AccountStore.get_active_auth_path() -> str | None`: returns the storage-state
	JSON file for the active account.
- `AIStudioClient.switch_auth(auth_file) -> None`: switches the gateway browser
	session to a different account storage-state file.
- `LoginSession.auth_switched: bool`: prevents repeated runtime auth switching
	when login status is polled after completion.

### 3. Contracts

- Startup browser warmup must load `AccountStore.get_active_auth_path()` before
	opening AI Studio when an active account exists.
- A newly saved login account becomes the active account unless a caller
	explicitly activates another account later.
- The first `GET /accounts/login/status/{session_id}` response that observes a
	completed login must switch the gateway client to the saved account auth file;
	subsequent polls must not repeatedly rebuild the browser session.
- When an auth file path is expected but missing or unreadable, session creation
	must fail with an auth-state diagnostic instead of silently creating an
	unauthenticated browser context.
- If navigation lands on `accounts.google.com` while opening AI Studio, errors
	must point to missing or invalid auth state.

### 4. Validation & Error Matrix

- Active account exists with auth JSON -> warmup/capture uses that auth file.
- Login completes and saves an account -> mark it active and switch runtime auth
	once during status polling.
- Login status is polled again after auth switch -> return completed status
	without another browser rebuild.
- Expected auth path does not exist -> raise an auth-file-missing error.
- AI Studio navigation redirects to Google sign-in -> raise an unauthenticated or
	invalid-auth-state diagnostic including URL/title/body context.

### 5. Good/Base/Bad Cases

- Good: User logs in, frontend polls status, saved account becomes active, client
	switches auth, and the first chat request reuses that account context.
- Base: Server restarts with an active account on disk, startup warmup loads its
	auth file before navigating to AI Studio.
- Bad: `settings.auth_file` is read once at process import and later login saves
	an account, but warmup/capture continues using the stale unauthenticated value.

### 6. Tests Required

- Unit-test that saving a login account makes it active and exposes an active
	auth path.
- Unit-test that completed login status switches runtime auth once.
- Unit-test startup wiring so warmup receives the active auth path.
- Unit-test Google sign-in redirects and missing auth files produce auth-state
	diagnostics, not generic chat-runtime timeouts.
- Run syntax checks over changed Python files and focused unit/smoke checks for
	account auth activation.

### 7. Wrong vs Correct

#### Wrong

```python
client = AIStudioClient(port=runtime_state.camoufox_port)
await client.warmup()
```

#### Correct

```python
client = AIStudioClient(port=runtime_state.camoufox_port)
auth_file = account_store.get_active_auth_path()
if auth_file:
    client.switch_auth(auth_file)
await client.warmup()
```
