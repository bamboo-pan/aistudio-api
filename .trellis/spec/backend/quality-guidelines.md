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

### Scenario: Src-Layout Subprocess Launchers Executed By File Path

#### 1. Scope / Trigger

- Trigger: Backend code starts a Python helper inside `src/` with `subprocess.Popen([python, path/to/helper.py, ...])` or an equivalent file-path execution command.
- Applies to browser, account, gateway, and other infrastructure helpers that must import `aistudio_api.*` while running as a child process.

#### 2. Signatures

- Parent process: `subprocess.Popen([python_executable, str(helper_path), ...], ...)`
- Helper path shape: `src/aistudio_api/.../<helper>.py`
- Package root that must be importable: repository `src/` directory.

#### 3. Contracts

- A helper executed by file path must not rely on the parent process having inserted `src/` into `sys.path`.
- Before importing `aistudio_api.*`, the helper must make the repository `src/` directory importable, or the parent must pass an environment that does so explicitly.
- Environment overrides such as `AISTUDIO_CAMOUFOX_PYTHON` may change the Python executable but must not remove the package import contract.

#### 4. Validation & Error Matrix

- Direct file execution cannot import `aistudio_api` -> startup bug; fix the helper/parent import path instead of documenting a manual `PYTHONPATH` requirement.
- Alternate Python executable lacks third-party runtime dependencies -> report the runtime dependency failure clearly; do not mask it as a package import-path issue.
- Existing `PYTHONPATH` is present -> preserve it when adding project paths from the parent process.

#### 5. Good/Base/Bad Cases

- Good: `python src/aistudio_api/infrastructure/browser/camoufox_launcher.py --help` succeeds from a source checkout.
- Base: Installed console scripts continue to work because the package is already importable.
- Bad: The server starts through root `main.py`, but the helper child process fails with `ModuleNotFoundError: No module named 'aistudio_api'`.

#### 6. Tests Required

- Add a regression test that executes the helper by file path with `--help` or another non-invasive argument and asserts exit code `0`.
- For browser/account/gateway startup changes, run a WSL real-environment check that exercises the same command shape used in production startup.

#### 7. Wrong vs Correct

##### Wrong

```python
from aistudio_api.config import settings

def main():
	...
```

##### Correct

```python
from pathlib import Path
import sys

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
	sys.path.insert(0, str(SRC_ROOT))

from aistudio_api.config import settings
```

---

### Scenario: Explicit UI Request Fields When Backend Defaults Differ

#### 1. Scope / Trigger

- Trigger: Frontend controls that map to API request fields where omission has backend semantics.
- Applies to Playground and other UI surfaces that call `/v1/chat/completions` or related API routes.

#### 2. Signatures

- API: `POST /v1/chat/completions`
- Relevant request field: `thinking: "off" | "low" | "medium" | "high"`

#### 3. Contracts

- UI `off` must be serialized as `thinking: "off"` when the control is available.
- UI `low` / `medium` / `high` must be serialized as the selected value.
- Omitted `thinking` is reserved for API-client default behavior and must not be used to represent an explicit UI off state.

#### 4. Validation & Error Matrix

- Unsupported model capability -> hide or disable the UI control before request construction.
- Invalid `thinking` value -> backend rejects with a bad request.
- Explicit UI off omitted from request -> bug, because backend may apply default-on behavior.

#### 5. Good/Base/Bad Cases

- Good: Thinking control available and set to off sends `{"thinking":"off"}`.
- Base: Thinking control unavailable sends no `thinking` field.
- Bad: Thinking control available and set to off sends no `thinking` field.

#### 6. Tests Required

- Static frontend regression: assert request construction includes the explicit off assignment.
- API compatibility tests: ensure non-off thinking values and backend defaults continue to behave as expected.
- Real environment check for chat/API request changes when the behavior depends on upstream AI Studio.

#### 7. Wrong vs Correct

##### Wrong

```javascript
if (controlAvailable('thinking') && cfg.thinking !== 'off') body.thinking = cfg.thinking;
```

##### Correct

```javascript
if (controlAvailable('thinking')) body.thinking = cfg.thinking;
```

### Scenario: Image Prompt Optimization Endpoint

#### 1. Scope / Trigger

- Trigger: Adding or changing the image prompt optimization API used by the static image generation UI.
- Applies when backend code introduces a UI-only helper endpoint that reuses text chat generation to prepare prompts for image models.

#### 2. Signatures

- API: `POST /v1/images/prompt-optimizations`
- Handler schema: `ImagePromptOptimizationRequest`
- Service entry point: `handle_image_prompt_optimization(req, client)`

#### 3. Contracts

- Request fields:
	- `prompt: string` — required, non-empty after trimming.
	- `model: string` — required by default schema fallback; must be a registered text-output model and must not be an image-output model.
	- `style_template: string` — one of the registered image style template ids; `none` preserves the original style direction.
	- `thinking: "off" | "low" | "medium" | "high" | bool | null` — forwarded only when the selected optimization model supports thinking; otherwise normalized to `off`.
- Response fields:
	- `object: "image_prompt_optimization"`
	- `model: string`
	- `style_template: string`
	- `style_label: string`
	- `options: [{ title: string, special: string, prompt: string }]` — exactly three items.
	- `usage` — optional chat usage from the underlying model call.

#### 4. Validation & Error Matrix

- Empty `prompt` -> `400 invalid_request_error`.
- Unknown `style_template` -> `400 invalid_request_error`.
- Unknown model -> `400 invalid_request_error`.
- Image-output model selected as optimizer -> `400 invalid_request_error`.
- Optimizer returns malformed JSON or not exactly 3 options -> `502 upstream_error`.

#### 5. Good/Base/Bad Cases

- Good: UI sends a raw prompt, `photorealistic`, `gemini-3-flash-preview`, and `thinking: "off"`; backend returns exactly three labeled prompt options.
- Base: UI selects a text model without thinking support; backend normalizes thinking to `off` and still optimizes.
- Bad: UI sends an image generation model as optimizer; backend rejects before any upstream call.

#### 6. Tests Required

- Service unit test: asserts exactly three returned options and style metadata.
- Service unit test: asserts non-off thinking is forwarded to capable text models.
- Service unit test: asserts thinking is normalized for text models without thinking support.
- API route test: asserts invalid style template returns `400` and does not call the client.
- Static frontend test: asserts UI exposes style templates, optimizer model selection, thinking control, endpoint path, and apply-option action.

#### 7. Wrong vs Correct

##### Wrong

```python
req = ChatRequest(model=image_model, messages=[...], thinking=user_thinking)
```

##### Correct

```python
capabilities = get_model_capabilities(req.model, strict=True)
if not capabilities.text_output or capabilities.image_output:
	raise _bad_request("optimizer model must be text-only")
thinking = req.thinking if capabilities.thinking else "off"
```

---

### Scenario: AI Studio Account Tier Detection

#### 1. Scope / Trigger

- Trigger: Code that detects, refreshes, or persists account `tier` from a browser-authenticated AI Studio page.
- Applies to `tier_detector`, `BrowserSession.detect_tier_for_auth_file`, account health checks, and tests around `/accounts/{id}/test`.

#### 2. Signatures

- Python API: `parse_account_tier_from_text(text: str | None, email: str | None = None) -> AccountTier`
- Python API: `detect_tier_sync(browser_context, timeout_ms: int = 30000) -> TierResult`
- Browser session API: `BrowserSession.detect_tier_for_auth_file(auth_file: str, timeout_ms: int = 30000) -> TierResult`
- HTTP API: `POST /accounts/{account_id}/test` may refresh the stored tier when a browser session is available.

#### 3. Contracts

- Stored tiers remain normalized to `free`, `pro`, or `ultra`.
- Explicit auth-file tier detection must test the provided `auth_file`; it must not require the active browser auth state to be configured first.
- Page detection must wait until `document.body.innerText` is available before evaluating DOM text.
- Detection should inspect account-context text such as the email account button and account menu, because AI Studio can expose `PRO`/`ULTRA` there instead of in a standalone header badge.
- Upgrade or marketing text such as `Upgrade to Google AI Pro` must not be treated as proof that the signed-in account is Pro.
- Logs, test artifacts, and task notes must not include cookies, tokens, or raw account identifiers beyond intentionally redacted values.

#### 4. Validation & Error Matrix

- `auth_file` missing -> raise the existing file/auth error path.
- Storage state cannot create a context -> fall back to applying cookies when supported; otherwise surface the existing invalid-auth error.
- Page redirects to Google sign-in -> report missing/invalid auth diagnostics without printing secrets.
- Body text never becomes available before timeout -> propagate a browser timeout/error.
- No account-context Pro/Ultra signal -> return `AccountTier.FREE`.

#### 5. Good/Base/Bad Cases

- Good: `<email> PRO` on the account button returns `AccountTier.PRO`.
- Good: account menu text containing `Manage membership` and `Google AI Ultra` returns `AccountTier.ULTRA`.
- Base: no premium account-context signal returns `AccountTier.FREE`.
- Bad: `Upgrade to Google AI Pro` returns `AccountTier.PRO`.
- Bad: checking a non-active account fails because no active auth is configured.

#### 6. Tests Required

- Unit tests for premium labels near the email/account menu context.
- Unit tests for upgrade/marketing text staying Free.
- Regression test that explicit `auth_file` detection does not call the active browser context warmup path.
- Real WSL credential test for browser/account-tier changes when upstream AI Studio DOM behavior is involved.

#### 7. Wrong vs Correct

##### Wrong

```python
self._ensure_browser_sync()
ctx = self._browser.new_context(storage_state=auth_file)
```

##### Correct

```python
self._ensure_browser_process_sync()
ctx = self._browser.new_context(storage_state=auth_file)
```

---

### Scenario: AI Studio Captured Request Model and Snapshot Cache Scope

#### 1. Scope / Trigger

- Trigger: Backend code captures, rewrites, replays, or caches AI Studio `GenerateContent` request templates.
- Applies to browser capture, pure HTTP capture, request rewriting, snapshot caching, and image/text generation paths that reuse captured request bodies.

#### 2. Signatures

- Cache API: `SnapshotCache.get(prompt: str, model: str | None = None) -> tuple | None`
- Cache API: `SnapshotCache.put(prompt: str, snapshot: str, url: str, headers: dict, body: str, model: str | None = None) -> None`
- Capture API: `RequestCaptureService.capture(prompt: str, model: str, ...) -> CapturedRequest | None`
- Replay API: `RequestReplayService.replay(captured, body: str, timeout: int | None = None) -> tuple[int, bytes]`
- Environment key: `AISTUDIO_TIMEOUT_REPLAY` controls non-streaming replay timeout in seconds.

#### 3. Contracts

- Captured templates are transport templates only; their embedded model must not override the model requested by the caller.
- Rewritten bodies must set wire field index `0` to the caller-requested model, normalized with the `models/` prefix during encoding.
- Snapshot cache entries for reusable prompt bodies must be scoped by both prompt and model to prevent a text-model/template body from being reused for an image-model request with the same prompt.
- Callers should omit replay `timeout` unless they intentionally need a per-call override; the default must flow from `settings.timeout_replay` / `AISTUDIO_TIMEOUT_REPLAY`.
- Image generation must use the same non-streaming replay timeout configuration as other non-streaming generation paths.

#### 4. Validation & Error Matrix

- Template body model differs from requested model -> rewrite to requested model before replay and logging.
- Same prompt is used with two different models -> cache lookup must return the entry for the matching model only.
- `timeout` is `None` at replay boundary -> use `settings.timeout_replay`.
- Large image generation times out with default replay timeout -> users can increase `AISTUDIO_TIMEOUT_REPLAY`; do not add hidden hard-coded image timeout values.

#### 5. Good/Base/Bad Cases

- Good: Capturing with a template body containing `models/gemini-3-flash-preview` and requested model `gemini-3.1-flash-image-preview` produces a captured body/log model of `models/gemini-3.1-flash-image-preview`.
- Good: `SnapshotCache` stores `("same prompt", "text-model")` and `("same prompt", "image-model")` as separate entries.
- Base: An explicit replay timeout override is still honored for a specialized caller.
- Bad: `RequestCaptureService` calls `modify_body(..., model=template.model or model)` and silently sticks to the template model.
- Bad: Cache key is only `prompt`, causing cross-model body reuse.
- Bad: Image generation passes `timeout=120` directly and ignores `AISTUDIO_TIMEOUT_REPLAY` changes.

#### 6. Tests Required

- Request rewriter unit test: template model differs from requested model and encoded body index `0` equals the requested model with `models/` prefix.
- Capture service regression: `CapturedRequest.model` reflects the requested model even when the captured template body contains another model.
- Snapshot cache regression: same prompt with different models returns separate cached bodies and misses for unrelated models.
- Real WSL credential test for browser/gateway/image changes that depend on upstream AI Studio behavior; set a non-default `AISTUDIO_TIMEOUT_REPLAY` and verify image generation succeeds without timeout.

#### 7. Wrong vs Correct

##### Wrong

```python
body = modify_body(template.body, model=template.model or model, prompt=prompt, snapshot=snapshot)
cached = snapshot_cache.get(prompt)
status, raw = await replay_service.replay(captured, body=body, timeout=120)
```

##### Correct

```python
body = modify_body(template.body, model=model, prompt=prompt, snapshot=snapshot)
cached = snapshot_cache.get(prompt, model=model)
status, raw = await replay_service.replay(captured, body=body)
```

---

## Testing Requirements

<!-- What level of testing is expected -->

(To be filled by the team)

---

## Code Review Checklist

<!-- What reviewers should check -->

(To be filled by the team)
