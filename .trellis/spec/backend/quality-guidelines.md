# Quality Guidelines

> Code quality standards for backend development.

---

## Overview

<!--
Document your project's quality standards here.

Questions to answer:
- What patterns are forbidden?
- What linting rules do you enforce?
- What are your testing requirements?
- What code review standards apply?
-->

(To be filled by the team)

---

## Forbidden Patterns

<!-- Patterns that should never be used and why -->

(To be filled by the team)

---

## Required Patterns

<!-- Patterns that must always be used -->

(To be filled by the team)

## Scenario: Gateway Replay Uses Captured Request Contract

### 1. Scope / Trigger

- Trigger: Browser-backed capture/replay code crosses capture service, replay service, streaming gateway, and browser session boundaries.
- Use this contract whenever replaying an AI Studio `GenerateContent` request captured from the browser.

### 2. Signatures

- `CapturedRequest.url: str`
- `CapturedRequest.headers: dict[str, str]`
- `CapturedRequest.body: str`
- `CapturedRequest.replay_headers: dict[str, str]`
- `BrowserSession.send_hooked_request(*, body: str, url: str, headers: dict[str, str], timeout_ms: int)`
- `BrowserSession.send_streaming_request(*, body: str, url: str, headers: dict[str, str], timeout_ms: int)`

### 3. Contracts

- Capture is responsible for returning a complete `CapturedRequest` containing the replay URL, original headers, and template body.
- Replay and streaming must pass `captured.url` and `captured.replay_headers` into `BrowserSession`; they must not ask the session to rediscover URL/header state from private template caches.
- `CapturedRequest.replay_headers` must exclude hop/body-length headers that browser XHR should not set manually: `host` and `content-length`.
- Pure HTTP replay may still use `captured.url` directly with an HTTP client and the same sanitized headers.

### 4. Validation & Error Matrix

- `captured is None` -> replay returns `(0, b"")` or streaming raises a clear captured-request error.
- Missing/invalid auth after replay reaches AI Studio -> propagate upstream authentication/authorization status.
- Empty session template cache with valid `CapturedRequest` -> replay must still send the browser XHR using captured URL/headers.

### 5. Good/Base/Bad Cases

- Good: A cached snapshot returns `CapturedRequest`; replay uses `captured.url` and succeeds without reading `BrowserSession._templates`.
- Base: A fresh capture returns `CapturedRequest`; replay and streaming both use the same captured URL/header contract.
- Bad: Account switching clears `BrowserSession._templates`, capture reuses a service-level cached template, and replay fails locally with `no captured URL available for replay`.

### 6. Tests Required

- Unit: non-streaming replay with a fake browser session that has no template cache; assert URL, sanitized headers, body, and timeout passed to `send_hooked_request`.
- Unit: streaming replay with a fake browser session that has no template cache; assert URL and sanitized headers passed to `send_streaming_request`.
- Integration/real: browser-backed `/v1/chat/completions` request returns an upstream result or upstream auth error, not local `no captured URL available for replay`.

### 7. Wrong vs Correct

#### Wrong

```python
return await self._session.send_hooked_request(body=body, timeout_ms=timeout * 1000)
```

#### Correct

```python
return await self._session.send_hooked_request(
	body=body,
	url=captured.url,
	headers=captured.replay_headers,
	timeout_ms=timeout * 1000,
)
```

##### Correct request-level image timeout override

```python
image_kwargs = {"prompt": prompt, "model": model}
if req.timeout is not None:
	image_kwargs["timeout"] = req.timeout
output = await client.generate_image(**image_kwargs)
```

```javascript
const timeout = this.normalizeImageTimeout()
const body = { model: this.imageModel, prompt, size: this.imageSize }
if (timeout) body.timeout = timeout
```

## Scenario: Browser Auth Changes Invalidate Capture State

### 1. Scope / Trigger

- Trigger: Code changes account activation, login completion, account rotation, browser auth switching, BotGuard snapshot retry, or request capture template caching.
- Use this contract whenever a browser-backed request may run after the active Google account or auth storage state changes.

### 2. Signatures

- `RequestCaptureService.clear_templates() -> None`
- `AIStudioClient.switch_auth(auth_file: str | None) -> None`
- `AIStudioClient.clear_capture_state() -> None`
- `AIStudioClient.clear_snapshot_cache() -> None`
- `AccountService.activate_account(account_id, browser_session, snapshot_cache, busy_lock=None, keep_snapshot_cache=False)` where `browser_session` should be the `AIStudioClient` when available, not only `AIStudioClient._session`.

### 3. Contracts

- Account activation must invalidate every cache that depends on the previous browser auth context: `BrowserSession` context/templates, `RequestCaptureService` per-model templates, and `SnapshotCache` prompt/model entries.
- `AIStudioClient.switch_auth` is the preferred auth-switch boundary because it can update the browser session and clear client-level capture state together.
- `AIStudioClient.clear_snapshot_cache` must clear capture templates as well as snapshots; a fresh snapshot with a stale captured template can still replay stale headers/body context.
- Streaming auth-error retry must call the client cache-clear boundary and then retry with `force_refresh_capture=True`.
- Replay must still use the `CapturedRequest` URL and sanitized headers after refresh; cache invalidation must not regress the captured request replay contract above.

### 4. Validation & Error Matrix

- Account switch succeeds -> next request for an already-used model re-captures its hook template before replay.
- Auth error during first streaming attempt -> clear capture state, force fresh capture, retry once.
- Retry still returns upstream `401`/`403` -> propagate the upstream auth/permission error; do not loop indefinitely.
- Missing account auth file -> activation returns no account and must not update the active account registry.
- Pure HTTP client has no browser templates -> clear snapshots and tolerate missing `clear_templates`.

### 5. Good/Base/Bad Cases

- Good: Web UI activates a different account; the next `gemini-3.1-flash-lite` request logs a fresh `Hook 模板已就绪` before replay.
- Base: Snapshot-only retry for the same auth context clears snapshots and templates, then captures fresh request state once.
- Bad: Account switching passes only `client._session` into `AccountService`, clearing browser templates but leaving `RequestCaptureService._templates` from the previous account.
- Bad: Streaming retry clears only `SnapshotCache`; the new snapshot is inserted into a stale template captured with old auth headers.

### 6. Tests Required

- Unit: `RequestCaptureService.clear_templates` causes the next same-model capture to call `capture_template` again.
- Unit: `AIStudioClient.switch_auth` clears service-level capture templates.
- Unit: account activation routes pass the runtime client into `AccountService.activate_account`.
- Unit: OpenAI and Gemini streaming auth-error retry clears capture state once and retries with `force_refresh_capture=True`.
- Integration/real: browser-backed `/v1/chat/completions` with the affected model returns SSE chunks and `[DONE]` using real account credentials.

### 7. Wrong vs Correct

#### Wrong

```python
result = await account_service.activate_account(
	next_account.id,
	client._session,
	runtime_state.snapshot_cache,
)
```

#### Correct

```python
result = await account_service.activate_account(
	next_account.id,
	client,
	runtime_state.snapshot_cache,
)
```

#### Wrong

```python
def clear_snapshot_cache(self) -> None:
	_snapshot_cache.clear()
```

#### Correct

```python
def clear_snapshot_cache(self) -> None:
	self.clear_capture_state()
```

## Scenario: Premium-Preferred Model Account Selection

### 1. Scope / Trigger

- Trigger: Code changes model capability metadata, account rotation, pre-request account selection, account tier detection, or text/image model routing.
- Use this contract whenever choosing which stored Google account should serve an AI Studio model request.

### 2. Signatures

- `AccountMeta.tier: str` with allowed values `free`, `pro`, `ultra`.
- `AccountMeta.is_premium -> bool` returns true for `pro` and `ultra`.
- `AccountRotator.model_prefers_premium(model: str | None) -> bool`.
- `AccountRotator.get_next_account(model: str | None = None, *, require_preferred: bool = False, exclude_account_id: str | None = None) -> AccountMeta | None`.
- `_ensure_account_for_model(model: str | None) -> None` runs before OpenAI/Gemini chat or image requests are sent upstream.

### 3. Contracts

- Premium-preferred models include registered `image_output` models and model IDs containing a standalone `pro` token, including IDs prefixed with `models/`.
- A standalone `pro` token is bounded by start/end, `-`, `_`, or `.`, so `gemini-3.1-pro-preview` and `gemini-pro-latest` match, while unrelated words containing `pro` should not.
- When the active account is non-premium and a healthy Pro/Ultra account exists, `_ensure_account_for_model` must switch to a Pro/Ultra account before capture/replay.
- When no Pro/Ultra account is available, preserve fallback behavior unless `require_preferred=True`: log the fallback and use an otherwise healthy account rather than failing locally.
- Account selection must use the same auth-switch boundary as manual activation, so browser session state, capture templates, and snapshot cache are invalidated together.

### 4. Validation & Error Matrix

- Registered image model + Pro/Ultra available -> select Pro/Ultra.
- Registered Pro text model + Pro/Ultra available -> select Pro/Ultra.
- `models/<pro-model>` prefixed ID -> same selection result as bare model ID.
- Premium-preferred model + no Pro/Ultra available + `require_preferred=False` -> warn and fall back to available healthy account.
- Premium-preferred model + no Pro/Ultra available + `require_preferred=True` -> return no account so caller can keep or report the current state.
- Non-premium text model -> use any healthy account according to the rotator mode.

### 5. Good/Base/Bad Cases

- Good: A newly activated Free account receives a `gemini-3.1-pro-preview` request while a Pro account is healthy; the request switches to the Pro account before capture and succeeds.
- Base: `gemini-3.1-flash-lite` stays on the active healthy Free account.
- Base: `gemini-3.1-flash-image-preview` continues to prefer Pro/Ultra accounts via image capability metadata.
- Bad: Only image models are premium-preferred; `gemini-3.1-pro-preview` stays on a Free account and upstream returns `[7,"The caller does not have permission"]`.

### 6. Tests Required

- Unit: `AccountRotator.model_prefers_premium` returns true for `gemini-3.1-pro-preview`, `models/gemini-3.1-pro-preview`, and `gemini-pro-latest`.
- Unit: Pro text model selection picks a Pro/Ultra account over a Free account.
- Unit/integration: OpenAI-compatible chat handling switches from a Free active account to an available Pro/Ultra account before calling the client for a Pro text model.
- Regression: Existing image model premium-selection tests still pass.
- Real: WSL browser-backed `/v1/chat/completions` for a premium-preferred model returns a successful upstream result and leaves the active account premium when a Pro/Ultra account is available.

### 7. Wrong vs Correct

#### Wrong

```python
def model_prefers_premium(self, model: str | None) -> bool:
	return get_model_capabilities(model, strict=True).image_output
```

#### Correct

```python
def model_prefers_premium(self, model: str | None) -> bool:
	capabilities = get_model_capabilities(model, strict=True)
	return capabilities.image_output or _model_name_prefers_premium(capabilities.id)
```

## Scenario: Account-Backed Runtime Statistics

### 1. Scope / Trigger

- Trigger: Code changes OpenAI, Gemini, image generation, streaming, prompt optimization, account rotation, or runtime stats recording.
- Use this contract whenever an upstream request is served by the currently active stored Google account.

### 2. Signatures

- `runtime_state.record(model: str, event: str, usage: dict | None = None, *, image_size: str | None = None, image_count: int = 1) -> None`
- `AccountRotator.record_success(account_id: str, *, image_size: str | None = None, image_count: int = 1) -> None`
- `AccountRotator.record_rate_limited(account_id: str) -> None`
- `AccountRotator.record_error(account_id: str) -> None`
- `_record_request_result(model, event, usage=None, *, image_size=None, image_count=1) -> None`

### 3. Contracts

- Model-level runtime stats and active-account stats must be recorded through the same request-result boundary when an active account exists.
- Success, error, and rate-limited events must update both model totals and account totals exactly once for each counted upstream request.
- Image generation success must pass `image_size` and the number of returned image items into both model and account stats.
- Transient retry attempts that clear stale capture state, such as first-attempt auth errors or empty image responses, must not be counted as permanent account errors unless the retry also fails.
- Web image generation and prompt optimization must refresh both `/stats` and `/rotation` after completion or failure so UI totals match backend state.

### 4. Validation & Error Matrix

- Active account exists + request succeeds -> model `success` increments and the same account `success` increments.
- Active account exists + upstream 429 with no successful retry -> model `rate_limited` increments and the same account `rate_limited` increments.
- Active account exists + final upstream error -> model `errors` increments and the same account `errors` increments.
- First auth/empty-image attempt clears capture state and retry succeeds -> only one success is counted, no account error is recorded.
- No active account exists -> model stats may be recorded, account stats are skipped.

### 5. Good/Base/Bad Cases

- Good: Web image generation on account A then account B leaves `/stats.totals.requests == 2` and the sum of `/rotation.accounts[*].requests == 2`.
- Base: OpenAI or Gemini streaming success records the final usage and updates the active account once after the stream completes.
- Bad: Streaming builders call only `runtime_state.record`, so model totals increase while account totals remain stale.
- Bad: A first-attempt stale capture `401` is counted as an account error even though a fresh-capture retry succeeds.

### 6. Tests Required

- Unit: non-streaming image success updates active-account requests, success, and image usage with the same image count as model stats.
- Unit: OpenAI and Gemini streaming success update active-account stats after completion.
- Unit: auth-error and empty-image retries clear capture state and do not count transient errors when the retry succeeds.
- Frontend/static: image generation and prompt optimization call a shared stats refresh that loads both `/stats` and `/rotation`.
- Real: WSL API and Web smokes activate two stored Pro accounts, generate images on both, and assert model totals equal account totals without printing secrets.

### 7. Wrong vs Correct

#### Wrong

```python
runtime_state.record(model, "success", output.usage)
```

#### Correct

```python
_record_request_result(model, "success", output.usage)
```

## Scenario: Image Model Capture with Proxied AI Studio Sessions

### 1. Scope / Trigger

- Trigger: Code changes browser session launch, proxy configuration, AI Studio navigation, image model selection, image onboarding, capture template caching, or image generation retry behavior.
- Use this contract for browser-backed image models such as `gemini-3.1-flash-image-preview` and `gemini-3-pro-image-preview`.

### 2. Signatures

- `settings.proxy_server: str | None`
- `settings.camoufox_locale: str`
- `settings.camoufox_timezone: str`
- `settings.camoufox_geolocation_latitude: float`
- `settings.camoufox_geolocation_longitude: float`
- `settings.camoufox_geolocation_accuracy: int`
- `camoufox_proxy_identity_options() -> dict[str, object]`
- `BrowserSession._prepare_model_onboarding_sync(page, model: str) -> bool`
- `BrowserSession._capture_template_request_with_recovery_sync(page, model: str) -> dict[str, Any]`
- `AIStudioClient.clear_capture_state() -> None`

### 3. Contracts

- Proxied Camoufox sessions must include stable locale, timezone, and geolocation hints from `camoufox_proxy_identity_options()` instead of enabling runtime `geoip=True`.
- Runtime `geoip=True` is not allowed in project code because it can require `camoufox[geoip]` and download GeoLite data from GitHub during real WSL tests.
- Image model capture must open the AI Studio image-generation entry, complete required onboarding/terms prompts, and select the UI model card matching the requested image model before template capture.
- Navigation to `ai.google.dev/gemini-api/docs/available-regions` is a recoverable redirect during capture setup; retry AI Studio chat navigation before failing.
- If the page leaves the chat runtime during template capture, reopen AI Studio, reinstall hooks, and retry capture once.
- If image replay returns a 200-shaped response with no parsed image data, clear capture state and retry once before returning a permanent upstream error.

### 4. Validation & Error Matrix

- Proxy configured -> Camoufox launch options include proxy plus `locale`, `config.timezone`, and `config.geolocation:*` values.
- AI Studio redirects to Google AI Developers available-regions docs -> navigation retries a chat URL and reports diagnostics only after retry failure.
- Image model requested -> image onboarding and model selection run before BotGuard snapshot/template capture.
- Template capture fill detaches because the page navigated away -> capture recovery reopens chat runtime and retries once.
- Empty image output on first attempt -> clear capture state and retry once; retry success returns `200` and records one success.
- Empty image output after retry -> return upstream error and record one final error.

### 5. Good/Base/Bad Cases

- Good: Account A generates `gemini-3-pro-image-preview`, account B generates the same model, then account A generates `gemini-3.1-flash-image-preview`; all three requests succeed and stats totals stay aligned.
- Base: A docs redirect during warmup is logged as a warmup failure but the next image capture opens a fresh browser context and succeeds.
- Bad: Enabling `geoip=True` makes WSL tests fail before the app starts because Camoufox tries to install or download GeoIP assets at runtime.
- Bad: Reusing a stale image template after an account switch returns `401` or a no-image response even though both stored accounts are valid Pro accounts.

### 6. Tests Required

- Unit: browser options and launcher options include proxy identity hints when `settings.proxy_server` is set.
- Unit: AI Studio docs redirect is retried and final diagnostics include the last URL/title/body when recovery fails.
- Unit: image model capture prepares onboarding/model selection before BotGuard snapshot readiness is required.
- Unit: template capture retries when a fill operation redirects or detaches the chat input.
- Unit: image generation retries one empty image response after clearing capture state and does not count the transient failure.
- Real: WSL API smoke uses a temporary copy under `/home/bamboo`, real accounts from `/home/bamboo/aistudio-api/data/accounts`, and verifies A -> B -> A image generation without printing credential contents.

### 7. Wrong vs Correct

#### Wrong

```python
options = {"proxy": {"server": settings.proxy_server}, "geoip": True}
```

#### Correct

```python
options = {"proxy": {"server": settings.proxy_server}}
options.update(camoufox_proxy_identity_options())
```

## Scenario: Browser Login Persists Only Verified Accounts

### 1. Scope / Trigger

- Trigger: Code changes browser-based Google account login, login status polling, account persistence, or post-login activation.
- Use this contract whenever a headed login browser captures Playwright storage state and may create a new account record.

### 2. Signatures

- `LoginSession.status: LoginStatus`
- `LoginSession.account_id: str | None`
- `LoginSession.email: str | None`
- `LoginSession.error: str | None`
- `AccountStore.validate_storage_state(storage_state: Any) -> str | None`
- `AccountStore.save_account(..., activate: bool = True) -> AccountMeta`
- `AccountService.activate_account(account_id, browser_session, snapshot_cache, busy_lock=None, keep_snapshot_cache=False) -> AccountMeta | None`

### 3. Contracts

- Browser login must validate captured storage state before saving it. A non-empty, non-expired Google cookie alone is not enough to prove the user finished login.
- Browser login must also detect authenticated account identity, preferably an email from the current page, `myaccount.google.com`, or validated storage-state local storage.
- If identity cannot be verified, the login session becomes `failed`, gets a clear error message, and must not create an account directory, registry entry, or active account.
- Browser-login-created accounts should be saved with `activate=False`; the account becomes active only after `AccountService.activate_account` switches the runtime browser/client auth successfully.
- Credential import can remain storage-state based and should not inherit the stricter headed-login identity gate unless that behavior is explicitly changed.

### 4. Validation & Error Matrix

- Storage state is malformed or has no valid Google cookie -> login session `failed`, no save.
- Storage state has Google cookies but no verified account identity -> login session `failed`, no save.
- Identity is detected and storage state is valid -> save account with `activate=False`, then login-status polling activates it through the runtime client.
- Activation fails after save -> report login/status failure; do not mark the saved account active.
- Existing imported/legacy accounts without email -> do not rewrite or delete them in the browser-login path.

### 5. Good/Base/Bad Cases

- Good: Login redirects away from `accounts.google.com`, email is found, storage state validates, account is saved inactive, and status polling activates it.
- Base: Login redirects but page email is missing; storage state local storage contains an email, so the account can still be saved inactive.
- Bad: Anonymous Google cookies validate structurally, the worker saves `email=None`, marks the account active, and later gateway calls fail with upstream auth/permission errors.

### 6. Tests Required

- Unit: fake login browser returns Google cookies without identity; assert session is `failed`, `account_id is None`, and the store remains empty.
- Unit: fake login browser returns a detected email; assert session is `completed`, account email is saved, and the store has no active account until activation.
- Unit/API: completed login status still activates a saved account exactly once through the runtime client.
- Real: WSL temp-copy validation uses the real accounts directory without printing credential contents and exercises at least one browser-backed `/v1/chat/completions` request.

### 7. Wrong vs Correct

#### Wrong

```python
meta = account_store.save_account(
	name=account_name,
	email=detected_email,
	storage_state=storage_state,
)
```

#### Correct

```python
detected_email = await self._verify_login_identity(account_store, page, storage_state, detected_email)
if detected_email is None:
	session.status = LoginStatus.FAILED
	session.error = LOGIN_IDENTITY_ERROR
	return

meta = account_store.save_account(
	name=account_name,
	email=detected_email,
	storage_state=storage_state,
	activate=False,
)
```

---

## Testing Requirements

<!-- What level of testing is expected -->

(To be filled by the team)

---

## Code Review Checklist

<!-- What reviewers should check -->

(To be filled by the team)
