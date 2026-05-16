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

## Testing Requirements

<!-- What level of testing is expected -->

(To be filled by the team)

---

## Code Review Checklist

<!-- What reviewers should check -->

(To be filled by the team)
