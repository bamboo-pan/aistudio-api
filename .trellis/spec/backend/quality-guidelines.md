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

## Scenario: Client-Compatible Chat/Responses/Messages Gateway

### 1. Scope / Trigger

- Trigger: Code changes OpenAI-compatible Chat Completions, OpenAI Responses, Anthropic Messages, Gemini-native conversion, tool normalization, or SSE event translation.
- Use this contract whenever a client-facing protocol payload is translated into the browser-backed AI Studio chat path.

### 2. Signatures

- `normalize_openai_tools_and_search(tools) -> tuple[list[list[Any]] | None, bool]`
- `normalize_openai_tools(tools) -> list[list[Any]] | None`
- `handle_openai_responses(payload: dict[str, Any], client, request: Request | None = None)`
- `handle_messages(payload: dict[str, Any], client, request: Request | None = None)`
- `handle_messages_count_tokens(payload: dict[str, Any]) -> dict[str, int]`
- `POST /v1/responses`
- `POST /v1/messages`
- `POST /v1/messages/count_tokens`

### 3. Contracts

- OpenAI-compatible search tools are recognized at the shared normalization boundary, not separately in each route. Supported types include `web_search`, `web_search_preview`, `web_search_preview_*`, `web_search_*`, `browser_search`, `google_search`, and `search`.
- Search tool requests must append the AI Studio `google_search` tool template while preserving valid function tools in the same request.
- Unknown non-function tools still fail validation; do not silently drop unsupported tool types.
- `/v1/chat/completions`, `/v1/responses`, and `/v1/messages` must share the same function-tool and search-tool normalization behavior.
- `/v1/responses` with `stream: true` must return SSE events including `response.created`, `response.in_progress`, text deltas, text done, output item done, `response.completed`, and final `data: [DONE]`.
- `/v1/messages` with `stream: true` must return Anthropic-compatible SSE events including `message_start`, content block start/delta/stop, `message_delta`, `message_stop`, and final `data: [DONE]`.
- `/v1/messages/count_tokens` returns `{"input_tokens": <int>}` using the same message/system/tool coercion assumptions as `/v1/messages`.
- These compatibility endpoints are practical subsets. Do not claim hosted OpenAI/Anthropic parity for background tasks, remote hosted tools, or provider-specific beta fields unless tests cover them.

### 4. Validation & Error Matrix

- Tool type `function` with a valid function object -> emit an AI Studio function declaration.
- Recognized search tool type -> set search enabled and append Google Search template.
- Recognized search tool plus function tools -> include both Google Search and function declarations.
- Unknown tool type -> `ValueError`/HTTP 400 with a clear unsupported tool message.
- Responses `stream: true` -> translate existing Chat SSE into Responses SSE; upstream stream errors become `response.failed` before `[DONE]`.
- Messages `stream: true` -> translate existing Chat SSE into Messages SSE; upstream stream errors become `error` before `[DONE]`.
- Empty or unsupported message content blocks -> preserve best-effort text while avoiding local crashes.

### 5. Good/Base/Bad Cases

- Good: CherryStudio sends `tools: [{"type":"web_search"}]` to `/v1/chat/completions`; the request uses Google Search and returns an OpenAI-compatible chat response.
- Good: Codex/Responses-style client sends `stream: true`; it receives Responses event names and a completed response containing accumulated output text.
- Good: Claude-compatible client sends `stream: true` to `/v1/messages`; it receives Anthropic event names and token usage deltas when available.
- Base: A request with only function tools behaves as it did before search-tool support.
- Bad: `/v1/chat/completions` accepts `web_search`, but `/v1/responses` rejects the same tool because it has a separate validator.
- Bad: Streaming wrappers emit text deltas but never emit done/completed events, leaving clients waiting.

### 6. Tests Required

- Unit: Chat Completions accepts each supported search-tool alias and appends the Google Search template.
- Unit: function tools and search tools can coexist without dropping either tool family.
- Unit: unknown tool types still fail with a clear validation error.
- Unit: Responses non-streaming output includes `web_search_call` when search was requested.
- Unit: Responses streaming includes `response.created`, text delta/done, `response.completed`, and `[DONE]`.
- Unit: Messages streaming includes `message_start`, text delta, `message_stop`, and `[DONE]`.
- Unit: `/v1/messages/count_tokens` returns `input_tokens` for system, messages, and tools payloads.
- Real: WSL browser-backed smoke must cover Chat search, Responses streaming, Messages streaming, and Messages count_tokens for API/gateway changes.

### 7. Wrong vs Correct

#### Wrong

```python
if tool.get("type") != "function":
	raise ValueError("Unsupported tool type")
```

#### Correct

```python
function_tools, uses_search = normalize_openai_tools_and_search(tools)
if uses_search:
	tool_blocks.append(TOOLS_TEMPLATES["google_search"])
```

#### Wrong

```python
if payload.get("stream"):
	raise ValueError("streaming is not supported")
```

#### Correct

```python
if payload.get("stream"):
	return _build_responses_streaming_response(payload, client, request)
```

## Scenario: Static Frontend API Surface Selection

### 1. Scope / Trigger

- Trigger: Code changes the built-in static frontend's model-list, chat, image-generation, or prompt-optimization request paths.
- Use this contract whenever the UI can choose between OpenAI-compatible `/v1` routes and Gemini-native `/v1beta` routes.

### 2. Signatures

- `modelListEndpoint() -> string`
- `normalizeModelList(data) -> list[dict]`
- `normalizeGeminiModel(item) -> dict`
- `chatRequestBody() -> dict`
- `geminiChatRequestBody() -> dict`
- `geminiChatEndpoint(stream=false) -> string`
- `geminiMessageFromPayload(payload) -> {content, thinking, usage}`
- `imageGenerationEndpoint() -> string`

### 3. Contracts

- OpenAI-compatible behavior must remain the default for models, chat, and images.
- Model-list selection may call `GET /v1/models` or `GET /v1beta/models`, but the UI's internal model shape must still include `id` and `capabilities` so controls do not guess from raw API payloads at render time.
- Gemini chat selection must translate the current transcript into `contents`, optional `systemInstruction`, optional `tools`, and optional `generationConfig` before calling `/v1beta/models/{model}:generateContent` or `:streamGenerateContent`.
- Gemini responses must be translated back to the existing transcript shape: assistant `content`, optional `thinking`, and normalized usage tokens.
- Image generation remains routed through `/v1/images/generations` until a real Gemini-native image endpoint exists; disabled UI options are allowed, silently broken selectable options are not.
- Account, rotation, stats, generated image files, and image-session endpoints are project management endpoints and must not be switched by the model/chat/image API selector.

### 4. Validation & Error Matrix

- Invalid stored API preference -> fall back to `openai` and keep loading the UI.
- Gemini model list lacks project-specific capabilities -> infer conservative capabilities from known model id patterns and `supportedGenerationMethods`.
- Selected model is missing after switching model-list API -> clear the previous model and select the first available model.
- Gemini chat stream event has `error` -> show the error on the assistant message and continue stream cleanup.
- Image API option has no backend implementation -> render it disabled and keep using the implemented OpenAI image endpoint.

### 5. Good/Base/Bad Cases

- Good: User switches model list to Gemini; the frontend calls `/v1beta/models`, strips the `models/` prefix for display, and still shows capability-driven controls.
- Good: User switches chat to Gemini with Stream enabled; the frontend calls `/v1beta/models/{model}:streamGenerateContent` and parses Gemini SSE chunks into the transcript.
- Base: User keeps defaults; existing `/v1/models`, `/v1/chat/completions`, and `/v1/images/generations` behavior is unchanged.
- Bad: A selector label says Gemini image generation is available, but clicking generate still sends an incompatible or nonexistent Gemini image request.
- Bad: Gemini model list is displayed raw and the rest of the UI loses capability gating for files, search, thinking, or image models.

### 6. Tests Required

- Unit/static: frontend exposes model, chat, and image API selectors.
- Unit/static: selectors persist in `localStorage` and default to OpenAI-compatible endpoints.
- Unit/static: Gemini model-list normalization and Gemini chat endpoint/body helpers are present.
- Unit/static: image generation goes through an endpoint helper that currently returns `/v1/images/generations`.
- Real: WSL smoke should serve `/static/index.html`, `/static/app.js`, `/v1/models`, and `/v1beta/models` from a temporary WSL copy with real account data available.

### 7. Wrong vs Correct

#### Wrong

```javascript
const r = await fetch('/v1/chat/completions', { method: 'POST', body: JSON.stringify(body) })
```

#### Correct

```javascript
if (this.chatApi === 'gemini') {
	return await this.completeGeminiChatFromCurrentMessages()
}
return await this.completeOpenAIChatFromCurrentMessages()
```

#### Wrong

```javascript
return data.models
```

#### Correct

```javascript
return data.models.map(item => this.normalizeGeminiModel(item)).filter(item => item.id)
```

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

- Trigger: Code changes OpenAI, Gemini, image generation, streaming, prompt optimization, account rotation, account-client pooling, or runtime stats recording.
- Use this contract whenever an upstream request is served by a stored Google account selected for that request. In pooled/balanced mode, the selected account may differ from the registry's current active account.

### 2. Signatures

- `runtime_state.record(model: str, event: str, usage: dict | None = None, *, image_size: str | None = None, image_count: int = 1) -> None`
- `AccountRotator.record_success(account_id: str, *, image_size: str | None = None, image_count: int = 1) -> None`
- `AccountRotator.record_rate_limited(account_id: str) -> None`
- `AccountRotator.record_error(account_id: str) -> None`
- `_record_request_result(model, event, usage=None, *, account_id=None, image_size=None, image_count=1) -> None`
- `RequestAccountContext.account_id -> str | None`

### 3. Contracts

- Model-level runtime stats and selected-account stats must be recorded through the same request-result boundary when a request-bound account exists.
- In account-client-pool mode, success, error, and rate-limit events must use `RequestAccountContext.account_id`; they must not read the current active account at record time.
- Legacy/no-pool paths may fall back to the current active account for stats only after account selection/activation has completed.
- Success, error, and rate-limited events must update both model totals and account totals exactly once for each counted upstream request.
- Image generation success must pass `image_size` and the number of returned image items into both model and account stats.
- Transient retry attempts that clear stale capture state, such as first-attempt auth errors or empty image responses, must not be counted as permanent account errors unless the retry also fails.
- Web image generation and prompt optimization must refresh both `/stats` and `/rotation` after completion or failure so UI totals match backend state.

### 4. Validation & Error Matrix

- Request-bound account exists + request succeeds -> model `success` increments and the selected account `success` increments.
- Request-bound account exists + upstream 429 with no successful retry -> model `rate_limited` increments and the selected account `rate_limited` increments.
- Request-bound account exists + final upstream error -> model `errors` increments and the selected account `errors` increments.
- First auth/empty-image attempt clears capture state and retry succeeds -> only one success is counted, no account error is recorded.
- No selected or active account exists -> model stats may be recorded, account stats are skipped.

### 5. Good/Base/Bad Cases

- Good: Web image generation on account A then account B leaves `/stats.totals.requests == 2` and the sum of `/rotation.accounts[*].requests == 2`.
- Base: OpenAI or Gemini streaming success records the final usage and updates the active account once after the stream completes.
- Good: Balanced mode request on account A records success on account A even if another request or manual action changes the active account before response accounting.
- Bad: Streaming builders call only `runtime_state.record`, so model totals increase while account totals remain stale.
- Bad: Request accounting reads `account_service.get_active_account()` after an upstream request handled by a pooled client, so stats can land on the wrong account.
- Bad: A first-attempt stale capture `401` is counted as an account error even though a fresh-capture retry succeeds.

### 6. Tests Required

- Unit: non-streaming image success updates active-account requests, success, and image usage with the same image count as model stats.
- Unit: account-pool chat success records the selected account and does not switch the active account.
- Unit: OpenAI and Gemini streaming success update selected-account stats after completion.
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
_record_request_result(model, "success", output.usage, account_id=account_context.account_id)
```

## Scenario: Balanced Account Pool Request Binding

### 1. Scope / Trigger

- Trigger: Code changes `round_robin` behavior, account rotation, account-client pooling, chat/image/Gemini request handling, streaming response builders, or 429 retry routing.
- Use this contract whenever a normal upstream request should be distributed across stored accounts without making the caller aware of backend account selection.

### 2. Signatures

- `RotationMode.ROUND_ROBIN == "round_robin"` remains the public config/API value and means balanced mode.
- `AccountRotator.acquire_account(model=None, *, require_preferred=False, exclude_account_id=None, affinity_key=None) -> AccountLease | None`.
- `AccountLease.account: AccountMeta` and `await AccountLease.release()`.
- `AccountStats.in_flight: int` is exposed through `/rotation.accounts[account_id].in_flight`.
- `AffinityBinding(account_id: str, created_at: float, expires_at: float)` stores bounded in-memory affinity.
- `DEFAULT_AFFINITY_TTL_SECONDS == 3600` unless overridden for tests.
- `/rotation.accounts[account_id].affinity_load: int` and `.bound_users: int` expose current non-expired logical user/session bindings.
- `/rotation.accounts[account_id].affinity_ttl_seconds: int` exposes the binding lifetime used by the running process.
- `AccountClientPool.get_client(account_id: str) -> AIStudioClient | None`.
- `ChatRequest.user: str | None` may be used as an OpenAI-compatible affinity hint.

### 3. Contracts

- Balanced `round_robin` must select per request using current in-flight count, historical request count, rate-limit count, and a round-robin tie breaker.
- A selected account lease must be held until the non-streaming request returns, or until the streaming generator finishes/cancels.
- Request handlers must use the pooled `AIStudioClient` associated with the selected account; they must not call global `activate_account()` for normal balanced routing.
- Each pooled client must have its own `SnapshotCache` and browser/capture/session state. Global active-account switching remains only for legacy/no-pool and manual activation flows.
- Lightweight affinity may keep a logical user/session on the same account when that account is not more than one in-flight request above the least-busy account.
- Affinity is intentionally temporary: a binding expires one hour after it is created and must not be refreshed indefinitely by repeated use.
- Expired affinity bindings must be pruned before selection and before `/rotation` stats are returned, so expired bindings do not count as account load.
- Account load is the count of non-expired affinity bindings assigned to an account; this is exposed as both `affinity_load` and the UI-friendly alias `bound_users`.
- For OpenAI-compatible chat, `ChatRequest.user` is the preferred affinity key. Without it, derive a bounded in-memory affinity key from normalized first user content.
- Account lease logs must include the selected request-bound account id, tier, mode, selection reason, in-flight count, affinity load, and affinity TTL. Do not log cookies, auth file contents, or prompt bodies beyond existing sanitized request logs.
- The admin UI must not use `激活/待命` as the serving-state label in balanced mode. Display pool scheduling state (`可调度`, `处理中`, `冷却中`, etc.) separately from a `默认账号` marker for the registry active account.
- On 429, update the failed selected account, then retry with `exclude_account_id` so the next attempt uses another eligible account when available.
- If stored accounts exist but no eligible account can be leased, do not silently use the global fallback client; return a service-unavailable style error or wait for the shortest cooldown when appropriate.
- Manual activation, login completion, credential import, account deletion, and force-next must invalidate affected pooled clients so stale auth/capture state is not reused.

### 4. Validation & Error Matrix

- Two concurrent leases + two healthy accounts -> selected account IDs differ and both `in_flight` values increment while leased.
- Same affinity key + account not overloaded -> selected account remains stable.
- Same affinity key after the one-hour binding TTL -> previous binding is ignored and the request participates in normal balanced selection again.
- `/rotation` after active bindings -> selected accounts report positive `affinity_load`/`bound_users` and `affinity_ttl_seconds == 3600`.
- Different `ChatRequest.user` values + two healthy accounts -> requests can distribute across accounts even with identical message content.
- Selected account 429 -> that account gets `rate_limited`, retry excludes it, and success can be recorded on another account.
- Pooled account auth changes -> next request creates a fresh pooled client for that account.
- All healthy accounts cooling down -> wait for shortest cooldown rather than sending through an unrelated global client.
- No stored accounts configured -> fallback client behavior remains available for legacy single-auth operation.

### 5. Good/Base/Bad Cases

- Good: Two real Pro accounts handle two OpenAI-compatible chat requests with different `user` values, and `/rotation` shows each account has one success and zero in-flight requests after completion.
- Good: The accounts table shows a healthy unused account as `可调度` with `0` bound users, not as a misleading standby serving state.
- Base: Exhaustion mode still keeps the active account until it becomes unavailable.
- Base: Premium-preferred model selection still filters eligible accounts to Pro/Ultra before balanced picking.
- Bad: A binding created for one logical user lasts forever and keeps the user pinned to one account even after the TTL window.
- Bad: Normal balanced routing calls `AccountService.activate_account()` before each request, racing global auth/capture state across concurrent users.
- Bad: A pooled request succeeds on account A but records stats on account B because the active account changed before accounting.
- Bad: The admin UI shows a request-serving pooled account as `待命`, implying it is not used.

### 6. Tests Required

- Unit: balanced concurrent leases distribute across two accounts and release `in_flight` counts.
- Unit: affinity keeps the same account when not overloaded.
- Unit: affinity load is exposed and expires after the TTL.
- Unit: account lease logs include selected account id and affinity load.
- Unit: different OpenAI `user` values distribute across pooled clients.
- Unit: pooled chat uses account-bound clients without switching the active account.
- Unit: 429 retry excludes the failed account and records stats on both the failed and successful accounts.
- Static/frontend: account table exposes pool status, default-account marker, and affinity load without `激活/待命` serving-state labels.
- Integration/real: WSL browser-backed `/v1/chat/completions` with two real accounts returns successful responses for two distinct user affinity keys and `/rotation` shows balanced account success counts.

### 7. Wrong vs Correct

#### Wrong

```python
await _ensure_account_for_model(model)
output = await client.generate_content(...)
_record_request_result(model, "success", output.usage)
```

#### Correct

```python
account_context = await _request_account_context(
	client,
	model,
	affinity_key=affinity_key,
	exclude_account_id=exclude_account_id,
)
output = await account_context.client.generate_content(...)
_record_request_result(model, "success", output.usage, account_id=account_context.account_id)
await account_context.release()
```

#### Wrong

```javascript
<span x-show="a.id===activeId">激活</span>
<span x-show="a.id!==activeId">待命</span>
```

#### Correct

```javascript
<span :class="poolStatusClass(a)" x-text="poolStatusLabel(a)"></span>
<div x-show="a.id===activeId">默认账号</div>
<strong x-text="accountLoad(a)"></strong>
```

## Scenario: Streaming Chat Success Requires Visible Output

### 1. Scope / Trigger

- Trigger: Code changes OpenAI-compatible streaming, Gemini streaming, stream parser/classifier, browser replay, frontend SSE consumption, or runtime stats for chat streams.
- Use this contract whenever converting AI Studio streaming replay events into downstream OpenAI/Gemini SSE responses.

### 2. Signatures

- `AIStudioClient.stream_generate_content(...) -> AsyncIterator[tuple[str, object | None]]`
- Stream event types: `"body"`, `"thinking"`, `"tool_calls"`, `"usage"`, `"done"`.
- `_build_streaming_response(...) -> StreamingResponse` for `/v1/chat/completions`.
- `_build_gemini_streaming_response(...) -> StreamingResponse` for `:streamGenerateContent`.
- `sse_error(message, error_type="upstream_error", code="upstream_error")` for OpenAI-compatible stream errors.
- Frontend stream consumer must handle top-level `{"error": ...}` SSE payloads in addition to `choices` and usage chunks.

### 3. Contracts

- A streaming response is successful only after at least one visible output event is emitted: `body`, `thinking`, or `tool_calls`.
- `usage` and `done` events alone are not visible assistant output and must not be recorded as success.
- If upstream finishes with HTTP 200 but no visible output, the backend must emit an SSE error chunk and `data: [DONE]`, and record the request as an error.
- OpenAI-compatible streams must preserve SDK-compatible error chunks with `error.message`, `error.type`, `error.param`, and `error.code`.
- Gemini-compatible streams must emit a Gemini-style `error` payload with code/status/message.
- The static frontend must surface top-level stream error chunks in the assistant message; it must not silently ignore them because the HTTP status is 200.

### 4. Validation & Error Matrix

- `body` event with non-empty text -> emit content delta, record success after stream completion.
- `thinking` event with non-empty text -> emit thinking delta, record success after stream completion.
- `tool_calls` event with at least one call -> emit tool-call delta, finish as tool calls, record success after stream completion.
- `usage` only + stream end -> emit upstream error chunk, send `[DONE]`, record errors.
- Upstream raises `AuthError`, `RequestError`, `UsageLimitExceeded`, or another `AistudioError` -> emit compatible stream error and `[DONE]`, record errors unless a first-attempt retry succeeds.
- Frontend receives `data: {"error": ...}` -> set the current assistant message error from `error.message`.

### 5. Good/Base/Bad Cases

- Good: AI Studio returns `pong`; OpenAI stream emits a content delta, stop chunk, usage chunk, and `[DONE]`.
- Base: AI Studio returns a tool call only; OpenAI stream emits `delta.tool_calls` and finishes with `tool_calls`.
- Base: AI Studio returns reasoning text before visible body; stream emits thinking chunks and still counts as visible output.
- Bad: Parser classifies every upstream chunk as `unknown`; backend emits only an empty stop chunk and records success.
- Bad: Backend emits an SSE error chunk, but the Web UI ignores it because it only reads `choices[0].delta`.

### 6. Tests Required

- Unit: OpenAI stream with a fake upstream `body` event emits content and records success.
- Unit: OpenAI stream with only `usage` emits a top-level error chunk and `[DONE]`.
- Unit: Gemini stream with only `usage` emits a Gemini error payload and `[DONE]`.
- Static/frontend: stream parser code checks `d.error` before usage/choice handling and writes it into the assistant message.
- Real: WSL browser-backed `/v1/chat/completions` stream for a text-only prompt returns at least one content delta and `[DONE]` with real account credentials.

### 7. Wrong vs Correct

#### Wrong

```python
async for event_type, text in upstream:
    if event_type == "usage":
        final_usage = text

_record_request_result(model, "success", final_usage)
yield sse_chunk(chat_id, model, "", finish="stop")
yield "data: [DONE]\n\n"
```

#### Correct

```python
saw_content = False
async for event_type, text in upstream:
    if event_type == "body" and text:
        saw_content = True
        yield sse_chunk(chat_id, model, text)
    elif event_type == "thinking" and text:
        saw_content = True
        yield sse_chunk(chat_id, model, "", thinking=text)
    elif event_type == "tool_calls" and text:
        saw_content = True
        yield sse_chunk(chat_id, model, "", tool_calls=to_openai_tool_calls(text))
    elif event_type == "usage":
        final_usage = text if isinstance(text, dict) else None

if not saw_content:
    raise RequestError(502, "AI Studio returned no response content")

_record_request_result(model, "success", final_usage)
```

#### Correct Frontend Error Handling

```javascript
const d = JSON.parse(line.slice(6))
if (d.error) {
  this.msgs[idx].error = d.error.message || JSON.stringify(d.error)
  continue
}
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
