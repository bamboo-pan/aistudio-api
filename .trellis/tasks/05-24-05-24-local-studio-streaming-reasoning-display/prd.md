# Fix Local Studio Streaming Reasoning Display

## Goal

Make Local Studio Responses stream runs preserve and display reasoning/thinking when reasoning is enabled, and make the real-system smoke test fail if the stream path loses thinking again.

## What I Already Know

* The current visible UI screenshot has `Reasoning > Effort` set to `off`, so that specific conversation is not expected to show a thinking block.
* The previous real WSL smoke did run a high-reasoning streaming Local Studio Responses case named `O-LS-06-reasoning-stream`.
* That run completed with status 200 but recorded `assistant_has_thinking: false`, while the non-stream case `API-LS-08-reasoning-nonstream` preserved `thinking` in the final assistant message.
* The UI renders a thinking block only when the assistant message has a non-empty `thinking` field.
* This is likely a backend stream/persistence issue or a final completed-conversation replacement issue, not just a UI styling issue.

## Requirements

* Preserve reasoning text in Local Studio streaming Responses final assistant messages when `reasoning_effort` is not `off` and the upstream/provider returns reasoning.
* Keep the UI behavior simple: if `message.thinking` exists, the existing thinking block should render; if reasoning is off or provider returns none, do not show a fake block.
* Tighten test coverage so the streaming reasoning case fails when thinking is dropped.
* Avoid changing unrelated provider/search/image behavior.

## Acceptance Criteria

* [ ] Local Studio streaming Responses high-reasoning path returns a completed conversation whose last assistant message has non-empty `thinking` when upstream emits reasoning.
* [ ] Local Studio non-stream Responses reasoning remains preserved.
* [ ] Static UI behavior still renders the existing thinking block for messages with `thinking`.
* [ ] The real-system smoke script asserts `O-LS-06-reasoning-stream` has `assistant_has_thinking: true`.
* [ ] Unit/static checks pass, and real WSL API/UI smoke is rerun for this bug.

## Definition of Done

* Focused unit tests pass.
* `node --check src/aistudio_api/static/app.js` passes if frontend code changes.
* Full `pytest` passes or an equivalent targeted suite is justified.
* WSL real API/UI smoke validates streaming reasoning display/persistence.
* No credentials, request-log exports, screenshots, generated images, or WSL artifacts are committed.

## Out of Scope

* Changing default reasoning from `off` to enabled.
* Forcing providers to generate reasoning when they return none.
* Redesigning the thinking block UI.

## Technical Notes

* Relevant previous evidence: `.trellis/tasks/archive/2026-05/05-24-local-studio-real-system-test-fixes/research/test-run-results.md`.
* Likely code surfaces: `src/aistudio_api/infrastructure/local_studio.py`, Local Studio route streaming handlers, and `src/aistudio_api/static/app.js` only if the final conversation replacement loses UI state.
* Current UI behavior: `src/aistudio_api/static/index.html` shows the think block via `x-if="m.thinking"`.
