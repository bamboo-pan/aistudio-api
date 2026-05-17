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

---

## Testing Requirements

<!-- What level of testing is expected -->

(To be filled by the team)

---

## Code Review Checklist

<!-- What reviewers should check -->

(To be filled by the team)
