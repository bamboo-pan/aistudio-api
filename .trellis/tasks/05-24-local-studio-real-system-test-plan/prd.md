# Local Studio Real System Test Plan

## Goal

Design and commit a new, complete, real-system frontend WebUI test plan for Local Studio and the surrounding WebUI. The plan must be grounded in the current architecture, use the real credential locations documented in `AGENTS.md`, and explicitly cover the two user-reported failures: Gemini image tool conversations failing after enabling the image tool, and custom OpenAI-compatible search conversations crashing the stream error path.

## Requirements

* Add a durable repository test-plan document under `tests/system/`.
* Cover the WebUI architecture as users encounter it: Playground, Local Studio, image generation, request logs, and account management remain independent entry points.
* Cover Local Studio as the high-level workbench: provider profile selection, interface modes, model loading, stream/non-stream, search, image tool, reasoning, attachments, cache, conversations, and request-log lifecycle.
* Treat Google AI Studio and custom OpenAI-compatible providers as distinct real provider paths with provider-specific expected behavior.
* Include both API-level and browser UI-level checks for the same user journeys.
* Use the real WSL testing setup from `AGENTS.md`: temporary WSL working directory, real Google AI Studio account credentials, and the OpenAI key file path.
* Do not commit secrets or test artifacts containing raw tokens, cookies, generated images, request logs, or browser storage states.
* Add the Trellis task files and include the existing `AGENTS.md` credential-path change in the final commit.

## Acceptance Criteria

* [x] The new plan enumerates the user-visible dimensions and the valid/invalid path combinations to test.
* [x] The plan includes explicit regression assertions for the Gemini image-tool bug and the OpenAI search streaming error bug.
* [x] The plan defines environment setup, credential handling, data isolation, artifact collection, and pass/fail gates.
* [x] The plan requires real API checks and real browser UI checks, not mocks or static-only tests.
* [x] The plan covers standalone base modules and confirms Local Studio wrapping does not regress them.
* [x] Markdown/document changes are checked for repository consistency.
* [x] The requested changes are committed on the feature branch.

## Definition of Done

* Repository test-plan document added.
* Trellis PRD, research, and context JSONL are present.
* Relevant verification for a documentation-only change is run.
* Commit includes this task's files and the existing `AGENTS.md` test-environment note.

## Technical Approach

The test plan will be a Chinese-language Markdown runbook and matrix in `tests/system/local-studio-web-real-system-test-plan.md`. It will define exhaustive user-path coverage by dimensions and then group high-cost real tests into suites that still cover every real user path: direct API preflight, browser navigation, provider setup, Local Studio provider/interface/tool combinations, request log lifecycle, standalone base-module smoke, failure-path robustness, and artifact/security gates.

## Decision (ADR-lite)

**Context**: The project already has unit/static tests, but the reported bugs only appear in full WebUI/API/provider chains with real credentials and request logging enabled.

**Decision**: Commit a dedicated system test plan under `tests/system/` rather than burying it in a Trellis task only. The Trellis task stores the reasoning; the repository file becomes the durable plan future agents and humans can execute.

**Consequences**: The plan is immediately visible next to tests and can later be converted into scripts. It intentionally references secret locations but never includes secret values.

## Out of Scope

* Fixing the two reported runtime bugs in this task.
* Implementing a full Playwright automation suite.
* Running expensive real provider tests for a documentation-only change.
* Changing Local Studio behavior or WebUI design.

## Technical Notes

* Architecture reference: `ARCHITECTURE.md`.
* Real testing instructions and credential locations: `AGENTS.md`.
* Local Studio frontend: `src/aistudio_api/static/index.html`, `src/aistudio_api/static/app.js`.
* Local Studio API: `src/aistudio_api/api/routes_local_studio.py`.
* Payload and persistence helpers: `src/aistudio_api/infrastructure/local_studio.py`.
* Request logging middleware: `src/aistudio_api/api/app.py`.
* Existing static/unit checks: `tests/unit/test_static_frontend_capabilities.py`, `tests/unit/test_local_studio.py`.

## Research References

* `research/current-test-surface.md` - inspected surfaces, credential boundaries, and bug-driven regression oracles.
