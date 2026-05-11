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

## Scenario: Credential Import / Export Safety

### 1. Scope / Trigger

- Trigger: Backend or WebUI changes import, export, display, validate, or restore
	account `auth.json` / Playwright storage-state credentials.
- Applies to credential backup packages and single-account storage-state JSON.

### 2. Signatures

- `GET /accounts/export` -> project credential backup package.
- `GET /accounts/{account_id}/export` -> single-account credential backup package.
- `POST /accounts/import` with JSON body -> `{ "imported": AccountResponse[], "count": number }`.
- `AccountStore.import_credentials(payload, name=None, activate=True) -> list[AccountMeta]`.

### 3. Contracts

- Export responses contain live cookies/tokens and must set `Cache-Control: no-store`
	and `Pragma: no-cache`.
- Backup packages use `format = "aistudio-api.credentials.backup"`, a supported
	integer `version`, a `manifest.warning`, and `accounts[].meta` plus `accounts[].auth`.
- Single-account imports accept Playwright storage state / `auth.json` objects with
	a non-empty `cookies` array and an optional `origins` array.
- Imported storage states must include at least one Google cookie domain such as
	`.google.com` or `accounts.google.com`.
- Backup package validation must complete for every account before writing any new
	account directories or registry entries.

### 4. Validation & Error Matrix

- Invalid JSON body -> `400` with a clear invalid JSON message.
- Non-object JSON body -> `400` with a JSON-object message.
- Unsupported backup `format` or `version` -> `400` / `ValueError` before saving.
- Empty or missing `cookies` -> `400` / `ValueError` before saving.
- Cookie missing `name`, `value`, `domain`, or `path` -> `400` / `ValueError` before saving.
- Storage state with no Google cookie -> `400` / `ValueError` before saving.
- Missing exported `auth.json` -> `400`; missing account id -> `404`.

### 5. Good/Base/Bad Cases

- Good: Validate all backup entries first, then save accounts and activate the
	requested active account only after successful validation.
- Base: Single storage-state import creates one account and activates it by default.
- Bad: Save the first account from a backup package, then reject a malformed second
	account and leave a partial restore behind.

### 6. Tests Required

- Store-level export test asserts `format`, `manifest.warning`, account metadata,
	and included auth payload.
- Store-level import tests cover single storage state, backup metadata restoration,
	malformed packages, non-Google cookies, and atomic validation before saving.
- Route-level export test asserts `Cache-Control: no-store` and `Pragma: no-cache`.
- Route-level import test asserts invalid JSON returns `400` without writing accounts.

### 7. Wrong vs Correct

#### Wrong

```python
for entry in payload["accounts"]:
		validate(entry)
		save_account(entry)
```

#### Correct

```python
validated = [validate(entry) for entry in payload["accounts"]]
for entry in validated:
		save_account(entry)
```

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

---

## Scenario: OpenAI-Compatible Image Generation Compatibility

### 1. Scope / Trigger

- Trigger: Backend changes OpenAI-compatible image generation routes, image-model
	metadata, or chat routing for models with image output capability.
- Applies when third-party clients such as Cherry Studio call image-capable models
	through `/v1/images/generations` or `/v1/chat/completions`.

### 2. Signatures

- `POST /v1/images/generations` with `ImageRequest` fields `prompt`, `model`,
	`n`, `size`, optional `response_format`, and declared OpenAI compatibility
	fields such as `quality`, `style`, `user`, `background`, `moderation`,
	`output_compression`, and `output_format`.
- `POST /v1/chat/completions` with an image-output model should route image
	generation semantics instead of failing because chat-only streaming is enabled.
- `GET /v1/models` and `GET /v1/models/{model}` expose image-generation
	metadata for image-capable models.

### 3. Contracts

- `response_format` may be omitted, `null`, `b64_json`, or `url`; the backend
	normalizes client variants to a usable generated-image response.
- `b64_json` responses keep the OpenAI-compatible `{ "data": [{ "b64_json": ... }] }`
	shape used by existing callers.
- `url` compatibility should not require public object hosting. When the backend
	only has image bytes, returning a data URL plus `b64_json` fallback is allowed.
- Chat requests selecting an image-output model must not expose unsupported
	streaming errors to users; the backend should downgrade/normalize streaming and
	return a client-consumable image result when practical.
- OpenAI-compatible public sizes must map to AI Studio's accepted wire values.
	For 1024-based sizes such as `1024x1024`, `1024x1792`, and `1792x1024`, send
	`output_image_size` as `1K`, not raw `1024`.
- Image size capability is model-specific. Do not share a single size list across
	all image-output models when real probes show different limits. In particular,
	`gemini-3.1-flash-image-preview` stays on the verified 512/1K sizes, while
	`gemini-3-pro-image-preview` may advertise and accept verified 2K/4K public
	sizes that map to `output_image_size` values `2K` and `4K`.
- Public square sizes should add a square prompt suffix such as
	`Use a square 1:1 composition.` before replay, because AI Studio's
	`output_image_size` token alone does not guarantee the requested aspect ratio.
- Unsupported image sizes remain hard validation errors because silently changing
	aspect ratio or resolution changes user intent.
- Image-generation metadata must describe the actual supported contract, not just
	the default request shape. Include supported `sizes`, `response_formats`, the
	`n` minimum/maximum/default, default `size` and `response_format`, explicit
	unsupported fields, and ignored compatibility fields.
- OpenAI compatibility fields that do not change AI Studio output must not be
	silently treated as supported. Either reject them before gateway calls or list
	them as explicitly ignored when their value is only for client-side tracking
	(for example `user`).

### 4. Validation & Error Matrix

- `n < 1` -> `400` before any gateway call.
- `n > 10` -> `400` before any gateway call.
- Unsupported image size -> `400` before any gateway call and include supported
	sizes or the rejected size in the message.
- Pro-only sizes such as `2048x2048` or `4096x4096` on
	`gemini-3.1-flash-image-preview` -> `400` before any gateway call.
- Unsupported effect/output fields such as `quality`, `style`, `background`,
	`moderation`, `output_compression`, or `output_format` -> `400` before any
	gateway call, with the field names in the message.
- Ignored compatibility fields such as `user` -> accepted without changing image
	generation output and documented in model metadata.
- Unknown extra fields -> `400` validation error; do not silently accept fields
	that are neither implemented nor documented as ignored.
- Non-image model used for image generation -> `400` with a model capability
	message.
- `response_format=url` -> compatible image response, not a format-only `400`.
- Chat request with image-output model and `stream=true` -> normalized image
	generation response or SSE chunks, not `does not support streaming responses`.

### 5. Good/Base/Bad Cases

- Good: Cherry Studio calls `/v1/images/generations` with an image model and
	either omits `response_format` or sends `url`; the backend returns a usable
	image payload without extra user configuration.
- Base: Existing callers send `response_format=b64_json`; response shape remains
	unchanged.
- Base: Clients send `user` for OpenAI request tracking; the backend accepts it
	but does not send it to AI Studio, and `/v1/models` marks it as ignored.
- Base: `gemini-3-pro-image-preview` accepts verified 2K/4K sizes such as
	`2048x2048` and `4096x4096`, appends the aspect-ratio prompt suffix, and maps
	them to `output_image_size` tokens `2K` and `4K`.
- Bad: Reject `response_format=url` solely because the gateway internally stores
	image bytes instead of public URLs.
- Bad: Advertise pro-only 2K/4K sizes on `gemini-3.1-flash-image-preview`, or
	accept a square public size while letting AI Studio return an unintended
	landscape/portrait aspect ratio.
- Bad: Accept `style=vivid` or `quality=hd` and then ignore it without metadata or
	a validation error.

### 6. Tests Required

- Unit-test `b64_json` response shape remains stable.
- Unit-test `url` compatibility includes a client-usable URL/data URL and does
	not remove the base64 fallback.
- Unit-test image-output models called through chat with `stream=true` do not
	fail capability validation.
- Unit-test unsupported size still fails before any client/gateway call.
- Unit-test supported public sizes map to AI Studio-accepted `output_image_size`
	values such as `512` and `1K`.
- Unit-test model-specific image size capabilities: flash image must reject
	pro-only 2K/4K sizes, and pro image must map verified high-resolution sizes to
	`2K`/`4K` wire tokens.
- Unit-test square public image sizes add a square aspect-ratio prompt suffix
	before gateway calls.
- Unit-test model metadata advertises the supported image response formats.
- Unit-test model metadata advertises image parameter defaults, ranges/enums,
	unsupported fields, ignored fields, and every public supported size.
- Unit-test unsupported image parameters fail before fake client/gateway calls;
	unit-test ignored fields such as `user` remain accepted.

### 7. Wrong vs Correct

#### Wrong

```python
if req.response_format != "b64_json":
    raise ValueError("response_format must be 'b64_json'")
```

#### Correct

```python
response_format = normalize_image_response_format(req.response_format)
return build_image_generation_response(output, response_format=response_format)
```

---

## Scenario: Capability-Driven Model Validation And UI Controls

### 1. Scope / Trigger

- Trigger: Backend changes model metadata, request validation, or frontend model
	controls for chat, image generation, tools, search, thinking, streaming, safety,
	or structured output.
- Applies across `GET /v1/models`, OpenAI-compatible routes, Gemini-compatible
	routes, and the static Alpine.js frontend.

### 2. Signatures

- `GET /v1/models` -> each item includes `capabilities` and optional
	`image_generation` metadata.
- `get_model_capabilities(model, strict=True) -> ModelCapabilities` is the
	backend source of truth for feature support.
- Frontend model records from `/v1/models` drive model picker options and
	settings controls.

### 3. Contracts

- Capability metadata must include text output, image input, image output, tool
	calls, search, thinking, streaming, structured output, safety settings, and
	unsupported generation fields when known.
- Backend validation must reject unsupported model/field combinations before
	replay/capture whenever the unsupported behavior can be detected locally.
- Frontend controls must be hidden, disabled, or reset when the selected model
	does not support the feature.
- Image-output models should route image-generation semantics instead of falling
	through to text-only chat validation.

### 4. Validation & Error Matrix

- Unknown model on strict public routes -> `404` or `400` with a model message.
- Image input sent to a text-only model -> `400` before gateway calls.
- Tools/search/thinking requested for a model without that capability -> `400`
	before gateway calls.
- Streaming requested for a non-streaming model -> normalize only when the route
	has an explicit compatibility behavior; otherwise return a clear `400`.
- Structured output requested for a model without structured output -> clear
	validation error, not a downstream wire failure.

### 5. Good/Base/Bad Cases

- Good: User selects an image model; text-only chat controls that do not apply
	are hidden or disabled, and image controls become available.
- Base: A model that supports search and thinking exposes both controls and the
	backend accepts the matching request fields.
- Bad: UI offers Search for an image model, sends `grounding=true`, then the
	gateway fails with a low-level wire error.

### 6. Tests Required

- Unit-test public model metadata includes every required capability field.
- Unit-test backend validation rejects unsupported combinations before the fake
	client/gateway is called.
- Static frontend tests or smoke checks must assert controls depend on
	capability metadata, not hardcoded model names.
- Run `node --check src/aistudio_api/static/app.js` when static JS changes.

### 7. Wrong vs Correct

#### Wrong

```javascript
if (model.includes('image')) cfg.stream = 'off';
```

#### Correct

```javascript
const capabilities = selectedModel.capabilities || {};
if (!capabilities.streaming) cfg.stream = 'off';
```

---

## Scenario: Real-Environment WSL Verification With Credentials

### 1. Scope / Trigger

- Trigger: A task changes account credentials, gateway replay/capture, model
	routing, frontend flows, or compatibility surfaces that need more confidence
	than unit tests alone.
- Applies when the user requests actual verification against the WSL home test
	environment.

### 2. Signatures

- WSL home root: `/home/bamboo`.
- Real credentials env: `AISTUDIO_ACCOUNTS_DIR=/home/bamboo/aistudio-api/data/accounts`.
- Verification record: `.trellis/tasks/<task>/verification.md`.

### 3. Contracts

- Create a fresh temporary directory under `/home/bamboo` for each real-environment
	verification pass.
- Use the real credential path only through environment variables or path
	existence checks.
- Do not print auth JSON, cookies, tokens, account IDs, or real account emails.
- Prefer non-destructive smoke tests. When mutation behavior needs coverage, use
	synthetic temp accounts unless the user explicitly asks to mutate real accounts.
- Record commands, pass/fail summaries, temp directory, and limitations in the
	task verification log.

### 4. Validation & Error Matrix

- WSL unavailable -> record blocker and run the closest local automated checks.
- Real credential directory missing -> record blocker; do not fabricate success.
- Node unavailable in WSL -> record limitation and use Windows `node --check` as
	the frontend syntax fallback.
- Live external request would consume quota or create content -> avoid by
	default; record that no live generation was sent.

### 5. Good/Base/Bad Cases

- Good: Full test suite runs in a WSL temp copy with `AISTUDIO_ACCOUNTS_DIR`
	pointing at the real credential directory, and smoke output is sanitized.
- Base: Read-only credential shape checks plus synthetic account mutations verify
	account logic without touching the real registry.
- Bad: Print a storage-state JSON snippet to prove the credential exists.

### 6. Tests Required

- Run the full relevant automated test suite in both the normal workspace and WSL
	when practical.
- Run focused smoke scripts for the changed feature area.
- Include `python -m compileall -q src tests` for backend changes.
- Include frontend syntax checks when static JS changes.

### 7. Wrong vs Correct

#### Wrong

```powershell
wsl cat /home/bamboo/aistudio-api/data/accounts/*/auth.json
```

#### Correct

```powershell
wsl env AISTUDIO_ACCOUNTS_DIR=/home/bamboo/aistudio-api/data/accounts \
  python verify_feature.py --redact-secrets
```

---

## Scenario: Pure HTTP Experimental Boundary

### 1. Scope / Trigger

- Trigger: `AISTUDIO_USE_PURE_HTTP` behavior, snapshot generation, browserless
	replay, streaming, image, tool, or structured-output support changes.
- Applies to gateway client/capture/replay code and user-facing docs.

### 2. Signatures

- `AISTUDIO_USE_PURE_HTTP=1` enables experimental browserless mode.
- `AIStudioClient(..., use_pure_http=True)` must expose clear support boundaries.

### 3. Contracts

- Pure HTTP mode is experimental unless a task fully proves browserless parity.
- Supported paths must be listed explicitly in README/docs.
- Unsupported paths must return clear `501`/unsupported errors, not generic
	`captured request is required`, missing session, or internal snapshot failures.
- Browser-required streaming must not silently run in pure HTTP mode.

### 4. Validation & Error Matrix

- Streaming in pure HTTP mode -> clear unsupported error.
- Image generation or image input in pure HTTP mode -> clear unsupported error.
- Tools, thinking, safety overrides, multi-turn, system instructions, or
	structured output not supported by the mode -> clear unsupported error.
- Missing BotGuard snapshot -> clear capture/snapshot error with no secret output.

### 5. Good/Base/Bad Cases

- Good: Plain single-turn non-streaming text requests are attempted only when all
	required snapshot inputs are available; everything else fails early with a
	clear message.
- Base: Docs and tests agree on what pure HTTP supports.
- Bad: A streaming request reaches `StreamingGateway` with `session=None` and
	exposes `browser session is required for streaming xhr replay` to users.

### 6. Tests Required

- Unit-test each unsupported route/feature boundary returns the documented error.
- Unit-test the supported plain-text request body shape when pure HTTP capture is
	available.
- WSL smoke should run focused pure HTTP boundary tests without live secret output.

### 7. Wrong vs Correct

#### Wrong

```python
return await streaming_gateway.stream_chat(captured=captured, session=None)
```

#### Correct

```python
if self._use_pure_http and stream:
    raise UnsupportedFeatureError("pure HTTP mode does not support streaming")
```

---

## Scenario: Account Health And Model-Tier Account Selection

### 1. Scope / Trigger

- Trigger: Backend changes account metadata, health checks, rotation, model-based
	account selection, or the account management UI.
- Applies to account store, account service, account rotator, public account
	routes, image generation, chat generation, and static account controls.

### 2. Signatures

- `AccountMeta` includes `tier`, `health_status`, `health_reason`,
	`last_health_check`, and `isolated_until`.
- `POST /accounts/{account_id}/test` -> sanitized account health result.
- `PUT /accounts/{account_id}` accepts `{ "name"?: string, "tier"?: "free" | "pro" | "ultra" }`.
- `AccountRotator.get_next_account(model=None, require_preferred=False)` selects
	a healthy account and may prefer Pro/Ultra accounts for image-output models.

### 3. Contracts

- Manual account tests must validate storage-state shape without returning or
	logging cookies, tokens, auth JSON, account ids, or real emails.
- Missing auth, expired cookies, repeated gateway errors, and active rate-limit
	cooldowns make an account unavailable for rotation.
- Image-output models prefer Pro/Ultra accounts when a healthy premium account is
	available; text models may use any healthy account.
- Fallback to a free account for image models is allowed only when no healthy
	premium account is available, and the fallback reason must be logged without
	identifying the account.

### 4. Validation & Error Matrix

- Unknown account on manual test/update -> `404`.
- Invalid tier -> `400` listing `free`, `pro`, and `ultra`.
- Missing auth file -> health status `missing_auth`, unavailable for rotation.
- Expired Google cookies -> health status `expired`, unavailable for rotation.
- Repeated gateway errors -> isolate the account for the configured cooldown or
	until explicitly repaired.

### 5. Good/Base/Bad Cases

- Good: An image request starts on a free active account, detects a healthy Pro
	account, switches auth once, clears snapshot cache, and sends the request.
- Base: A text request uses the active healthy free account.
- Bad: Image generation repeatedly uses a known expired account because the
	rotator only looks at round-robin position.

### 6. Tests Required

- Unit-test valid, expired, and missing-auth health checks.
- Route-test `/accounts/{id}/test` response is sanitized.
- Unit-test tier updates and invalid-tier rejection.
- Unit-test premium preference, free fallback logging, rate-limit availability,
	error isolation, and image-request auth switching.
- WSL verification must inspect real credentials read-only and use synthetic
	accounts for mutation/isolation checks.

### 7. Wrong vs Correct

#### Wrong

```python
return await rotator.get_next_account()
```

#### Correct

```python
await _ensure_account_for_model(model)
```

---

## Scenario: Compatibility Routes With Clear Unsupported Boundaries

### 1. Scope / Trigger

- Trigger: Backend changes OpenAI-compatible `/v1/*` routes or Gemini-native
	`/v1beta/*` compatibility surfaces.
- Applies to `/v1/responses`, `/v1/messages`, `/v1/chat/completions`,
	`/v1beta/models`, `countTokens`, embeddings, cached content, safety settings,
	and file data handling.

### 2. Signatures

- `POST /v1/responses` accepts `model`, `input`, optional `text.format`,
	`response_format`, and non-streaming tool-compatible payloads.
- `POST /v1/messages` accepts Anthropic-style `system`, `messages`, and `tools`
	then maps them to chat generation.
- `GET /v1beta/models` returns Gemini-style model records and supported methods.
- `POST /v1beta/{model}:countTokens` returns an estimated `totalTokens` without
	downstream replay.

### 3. Contracts

- OpenAI-compatible routes should return OpenAI-style `{ "error": ... }` envelopes
	for request errors.
- Structured output must be gated by model capabilities and mapped to generation
	config overrides only for models that support it.
- Tool-call arguments exposed through OpenAI or Anthropic-compatible responses
	must be JSON strings or parsed JSON according to the target API shape.
- Unsupported Gemini-native surfaces such as embeddings, `cachedContent`,
	`safetySettings`, and `fileData` must fail early with a clear unsupported or bad
	request message instead of reaching browser replay.

### 4. Validation & Error Matrix

- Missing `model` on OpenAI compatibility routes -> `400` OpenAI-style error.
- `/v1/responses` or `/v1/messages` with `stream=true` -> clear `400` until
	streaming variants are implemented.
- Structured output requested for a model without support -> `400` before replay.
- Gemini embeddings/batch embeddings -> `501 unsupported_feature`.
- `cachedContent`, `safetySettings`, or `fileData` in browser replay mode -> clear
	`400` explaining the unsupported field.

### 5. Good/Base/Bad Cases

- Good: `/v1/responses` with `text.format.type=json_schema` produces JSON output
	and passes schema overrides to the gateway.
- Base: `/v1beta/models` advertises `generateContent`, `streamGenerateContent`,
	and `countTokens` according to model capability.
- Bad: A `fileData` Gemini request enters replay and fails with an opaque wire
	decode error.

### 6. Tests Required

- Route-test `/v1/responses`, `/v1/messages`, and OpenAI error envelopes.
- Unit-test response-format/json-schema override mapping and model capability
	rejection.
- Route-test Gemini model listing, count tokens, embeddings unsupported errors,
	and unsupported Gemini fields.
- WSL smoke may use fake clients for compatibility routes to avoid quota use.

### 7. Wrong vs Correct

#### Wrong

```python
return await handle_chat(ChatRequest(**payload), client)
```

#### Correct

```python
chat_req = ChatRequest(model=model, messages=coerced_messages, response_format=response_format)
return await handle_chat(chat_req, client)
```

---

## Scenario: Streaming Response Stability

### 1. Scope / Trigger

- Trigger: Backend changes OpenAI SSE streaming, Gemini streaming, tool-call
	deltas, usage trailers, disconnect handling, or temporary image cleanup.
- Applies to stream builders, gateway streaming clients, and request normalizers
	that create temporary files.

### 2. Signatures

- `_build_streaming_response(..., request=None)` returns OpenAI-compatible SSE.
- `_build_gemini_streaming_response(..., request=None)` returns Gemini-compatible
	SSE.
- Streaming gateway iterators should support `aclose()` cleanup when available.

### 3. Contracts

- Stream error chunks must be SDK-compatible and terminate with `data: [DONE]`.
- Tool-call streaming deltas must include stable indexes and JSON string
	arguments for OpenAI-compatible chunks.
- Gemini streaming tool calls must emit `functionCall` parts and finish with
	`FUNCTION_CALL` when tool calls were seen.
- Client disconnects before or during upstream streaming must close upstream
	iterators and remove temporary image files.
- Normalizers that create temp files from data URLs or inline data must clean
	them if later validation rejects the request.

### 4. Validation & Error Matrix

- Upstream `RequestError(501, ...)` during stream -> unsupported error payload and
	`[DONE]`.
- Upstream auth/rate-limit/gateway error during stream -> typed error payload and
	`[DONE]`.
- Disconnect before downstream call -> no downstream call and temp files removed.
- Disconnect during downstream stream -> upstream `aclose()` invoked and temp
	files removed.

### 5. Good/Base/Bad Cases

- Good: A tool-call stream emits delta, usage trailer, function-call finish, and
	then `[DONE]`.
- Base: A plain text stream yields body chunks and cleans uploaded image temp
	files on normal completion.
- Bad: A client disconnect leaves an async generator blocked and an uploaded
	image temp file on disk.

### 6. Tests Required

- Unit-test OpenAI stream error shape and `[DONE]` marker.
- Unit-test OpenAI and Gemini tool-call chunks and usage trailers.
- Unit-test stream iterator close/disconnect cleanup for OpenAI and Gemini paths.
- Unit-test normalizer cleanup after late validation failures.
- WSL smoke can use fake streaming clients and direct iterator disconnect
	simulation; do not require live external generation.

### 7. Wrong vs Correct

#### Wrong

```python
async for event in client.stream_generate_content(...):
    yield event
```

#### Correct

```python
upstream = client.stream_generate_content(...)
try:
    async for event in upstream:
        if await _request_disconnected(request):
            return
        yield convert(event)
finally:
    await _close_async_iterator(upstream)
```
