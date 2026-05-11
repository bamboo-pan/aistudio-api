# P0/P1 Actual Verification Implementation

## Goal

Bring the project from a partially complete AI Studio gateway to a reliably usable P0 + P1 feature set, implementing P0 first and P1 second. Every delivered item must include practical verification in a temporary directory under WSL home, using the real account credentials directory supplied by the user, with sensitive values redacted from logs.

## What I Already Know

* Current repo already has partial implementations for image generation compatibility, a model capability registry, credential import/export, account rotation stats, OpenAI/Gemini routes, and unit tests.
* Current unit test baseline passes on Windows: `66 passed`.
* User requires actual verification for all tasks, not only unit tests.
* Verification must create a new temporary directory under WSL Ubuntu home: `\\wsl.localhost\Ubuntu-24.04\home\bamboo`, corresponding to `/home/bamboo` inside WSL.
* Real credentials live at `\\wsl.localhost\Ubuntu-24.04\home\bamboo\aistudio-api\data\accounts`, corresponding to `/home/bamboo/aistudio-api/data/accounts` inside WSL.
* Verification must avoid printing cookie/token/auth JSON contents.

## Requirements

### Execution Order

* Complete P0 before starting P1 feature implementation.
* Do not treat an item as done until both automated tests and WSL actual verification are recorded.
* Keep a verification log at `verification.md` in this task directory with command summaries, temp directory path, result, and any limitations.

### P0 Must Do

1. Fix image model support.
   * Image models must not receive incompatible generation config fields such as `mediaResolution`.
   * `/v1/images/generations` must handle `size`, `n`, `response_format`, image return format, friendly error format, and regression tests.
   * Existing partial implementation must be audited and completed rather than duplicated.
2. Establish a model capability registry.
   * Each model must expose capabilities for text output, image input, image output, tool calls, search, thinking, streaming, structured output, and unsupported fields.
   * Backend validation must use the registry before sending requests downstream.
   * Frontend must consume the registry to show, hide, or disable model-dependent controls.
3. Credential import/export/backup restore.
   * Support existing `auth.json`, Playwright storage state, and project backup packages.
   * Support single-account and all-account export.
   * Import must validate cookie shape, Google cookie presence, account email when available, and expired/obviously invalid cookie state when detectable.
   * Export must either encrypt or clearly warn; MVP may keep warning-only if documented and visible.
4. Align frontend settings with backend capabilities.
   * Search, Thinking, Safety, Stream, and related controls must map to backend fields.
   * Controls unavailable for the selected model must be hidden or disabled based on `/v1/models` metadata.
5. Complete test and dependency baseline.
   * Declare missing runtime/dev dependencies, including `aiohttp` if pure HTTP replay still imports it.
   * Add CI or equivalent repeatable test command definition.
   * Add regression tests for P0 changes.
6. Request validation and friendly errors.
   * Validate empty messages, illegal roles, invalid model, unsupported fields for image models, oversized images, invalid `temperature` / `top_p` / similar numeric parameters before downstream calls.
   * Translate lower-level wire/client errors into user-readable API errors.

### P1 High Value

7. Account pool health management.
   * Add account health checks, login-expiry detection where practical, rate-limit state, Pro/Ultra/free labels, manual account test, and automatic isolation of bad accounts.
8. Select accounts by model.
   * Image models should prefer Pro/Ultra accounts when available.
   * Text models may use normal accounts.
   * If the preferred account class is unavailable, fallback/switch behavior must be clear and logged.
9. Complete frontend image features.
   * Chat page supports image upload.
   * Add a dedicated image generation page with model, size, count, result gallery, download, failure retry, and local history.
10. Expand OpenAI compatibility.
   * Add `/v1/responses`, `/v1/messages`, more complete `response_format` / `json_schema`, tool-call streaming deltas, and standard OpenAI error shape where practical.
11. Complete Gemini native APIs.
   * Add `/v1beta/models`, `countTokens`, `embedContent`, `batchEmbedContents`, `safetySettings`, `cachedContent`, and `fileData` behavior or clear unsupported errors.
12. Improve streaming stability.
   * Client disconnect should cancel downstream work and clean temporary files where the stack allows.
   * Streaming errors, usage endings, and tool-call chunks should be more compatible with common OpenAI/Gemini SDK expectations.
13. Clarify pure HTTP mode boundaries.
   * Either complete non-browser support for dependencies, snapshot, non-streaming, and streaming paths, or mark the mode experimental and return clear errors for unsupported cases.

## Acceptance Criteria

### P0 Gate

* [ ] Automated tests pass after P0 changes.
* [ ] WSL temp verification directory is created under `/home/bamboo` and recorded.
* [ ] WSL verification uses `AISTUDIO_ACCOUNTS_DIR=/home/bamboo/aistudio-api/data/accounts` without printing secrets.
* [ ] Image generation works or fails with a clear external-service/account error, never with `MediaResolution is not supported` from our request construction.
* [ ] `/v1/models` exposes all required capability fields, including structured output.
* [ ] Frontend controls reflect model capabilities from `/v1/models`.
* [ ] Credential import/export is tested with safe synthetic credentials and, where possible, non-destructive validation against the real credentials directory.
* [ ] Invalid request cases return clear 4xx errors with consistent shape.
* [ ] Missing dependencies/CI baseline are fixed and verified.

### P1 Gate

* [ ] Automated tests pass after P1 changes.
* [ ] WSL actual verification is re-run after P1 changes in a fresh temp directory or clean test copy.
* [ ] Account health, tier, manual test, rate-limit, and isolation behavior are verifiable without exposing credential contents.
* [ ] Model-based account selection behavior is exercised and logged.
* [ ] Frontend image upload and image page are manually smoke-tested in WSL server mode.
* [ ] New OpenAI and Gemini routes have route-level tests and clear unsupported behavior where full implementation is not possible.
* [ ] Streaming and pure HTTP boundary behavior are covered by automated tests plus WSL smoke checks.

## Definition of Done

* P0 implementation and verification complete before P1 implementation begins.
* Unit/regression tests pass locally.
* WSL actual verification artifacts are recorded in `verification.md`.
* No credential/token/cookie values are committed or printed in final summaries.
* Documentation is updated when public behavior, routes, env vars, or setup changes.
* Any remaining gaps are explicitly listed with reason and recommended next step.

## Technical Approach

* Extend existing modules rather than replacing them: `domain/model_capabilities.py`, `api/schemas.py`, `application/api_service.py`, `application/chat_service.py`, `application/account_service.py`, `infrastructure/account/*`, and static Alpine UI files.
* Use Pydantic validation or explicit service-layer validation before downstream wire replay.
* Use existing `AccountStore`, `AccountRotator`, and stats structures as the base for account health and selection.
* Add route-level tests for public API behavior and unit tests for validation/planning logic.
* For WSL verification, copy or install the current project into a temporary `/home/bamboo/aistudio-api-verify-*` directory, point `AISTUDIO_ACCOUNTS_DIR` at `/home/bamboo/aistudio-api/data/accounts`, run tests/smoke checks, and record sanitized results.

## Decision (ADR-lite)

**Context**: The requested scope spans API compatibility, account management, frontend controls, verification infrastructure, and real-account smoke testing. Some parts are partially implemented, so wholesale rewrites would increase risk.

**Decision**: Proceed in two gates: P0 completion first, then P1. Each gate must include automated tests plus WSL real-environment verification before being considered complete.

**Consequences**: This keeps the work safer and auditable, but the overall task is large. Some P1 items may need clear unsupported behavior instead of full external-service feature parity if Google/AI Studio wire behavior cannot be safely implemented in one pass.

## Out of Scope

* P2 and P3 productization items unless they are strictly necessary to satisfy P0/P1 safety or verification.
* Printing, copying into logs, or committing real credential contents.
* Pushing to a remote repository.
* Long-lived production deployment from the WSL temporary verification directory.

## Technical Notes

* Existing model capability registry: `src/aistudio_api/domain/model_capabilities.py`.
* Existing OpenAI routes: `src/aistudio_api/api/routes_openai.py`.
* Existing Gemini routes: `src/aistudio_api/api/routes_gemini.py`.
* Existing account credential import/export: `src/aistudio_api/infrastructure/account/account_store.py` and `src/aistudio_api/api/routes_accounts.py`.
* Existing frontend is static Alpine.js under `src/aistudio_api/static/`; avoid adding a build step unless absolutely required.
* Current test command: `python -m pytest -q`.