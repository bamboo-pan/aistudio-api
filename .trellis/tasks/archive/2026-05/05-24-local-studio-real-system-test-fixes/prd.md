# Local Studio Real System Test Fixes

## Goal

Execute the Local Studio WebUI real system test plan end to end in a fresh WSL environment, collect all discovered bugs, fix them in focused batches, rerun the complete system test plan until P0/P1 acceptance criteria pass, then finish with Trellis-compliant verification and commits.

## What I Already Know

* The user supplied `LOCAL_STUDIO_WEB_REAL_SYSTEM_TEST_PLAN.md` as the authoritative test plan.
* The test plan requires a fresh WSL copy under `/home/bamboo`, real Google AI Studio account credentials from `/home/bamboo/aistudio-api/data/accounts`, and the OpenAI-compatible key from `/mnt/c/Users/bamboo/Documents/github/key.txt`.
* Non-documentation changes must be validated with real API-level and browser UI-level tests.
* Request logging must be enabled and verified for lifecycle completeness and secret redaction.
* P0 regressions to cover include Google Responses image-tool invocation config, OpenAI-compatible Responses search streaming error handling, OpenAI-compatible search tool type mapping, and Responses reasoning preservation.
* The likely implementation surfaces include `src/aistudio_api/api/routes_local_studio.py`, `src/aistudio_api/infrastructure/local_studio.py`, request-log routes/middleware, and `src/aistudio_api/static/` frontend assets.

## Requirements

* Run the real system test plan from a WSL temporary copy, not directly against the development workspace.
* Preserve secrets: do not print or commit real tokens, cookies, storage state, request-log exports with secrets, screenshots containing secrets, or generated images.
* Execute an initial real test pass to identify current failures before changing behavior.
* Group discovered failures by root cause, then fix them in focused code changes following existing project patterns.
* Re-run relevant unit/static checks after fixes and run the full real system test plan again.
* Repeat fix and full real-test cycles until all P0 and P1 checks pass, or stop only on a genuine external blocker that cannot be resolved locally.
* Maintain Local Studio provider/interface/tool/reasoning/cache isolation and request-log lifecycle guarantees from the plan.
* Verify base modules (`#chat`, `#images`, `#requests`, `#accounts`) remain independent of Local Studio provider configuration.
* Follow the repository development workflow: feature branch from `master`, Trellis task artifacts, merge latest `origin/master` before final verification, then commit recognized task changes.

## Acceptance Criteria

* [ ] Initial WSL real-system run produces a bug summary with API evidence, UI evidence, server stderr summary, request-log group ids where available, and screenshots for critical paths.
* [ ] All code fixes are root-cause focused and covered by targeted automated tests where feasible.
* [ ] Full WSL real-system rerun passes P0 and P1 requirements from `LOCAL_STUDIO_WEB_REAL_SYSTEM_TEST_PLAN.md`.
* [ ] OpenAI-compatible Responses search sends `web_search`, never `web_search_preview`, and streaming 4xx failures produce controlled SSE errors without ASGI exception groups or `httpx.ResponseNotRead`.
* [ ] Google AI Studio Responses search continues to send `web_search_preview`, and image-tool flows do not require missing `include_server_side_tool_invocations` configuration.
* [ ] Reasoning/tool/search/image details returned by upstream providers are preserved in API responses, UI state, conversation persistence, request logs, refresh recovery, rerun, and cache hit paths where applicable.
* [ ] Cache hits do not cross provider, interface, model, tool, reasoning, attachment, token hash, or namespace boundaries.
* [ ] Request logs contain complete lifecycle stages for success and failure paths and remain redacted.
* [ ] No real credentials or generated artifacts are committed.
* [ ] Trellis PRD/context files and task metadata are committed with the work.

## Definition of Done

* Targeted automated tests pass.
* Real WSL system tests pass for API and browser UI paths required by the plan.
* Server logs are checked for ASGI exceptions and secret leakage.
* Request-log exports used as evidence are checked for redaction before being kept in temporary artifacts.
* Relevant `.trellis/spec/` updates are made if this work reveals durable conventions or pitfalls.
* Work is committed on the feature branch after merging latest `origin/master`.

## Technical Approach

1. Prepare a clean feature branch and Trellis task.
2. Create a WSL temporary repo copy with isolated runtime data directories and request logs.
3. Turn the supplied plan into reusable smoke scripts where useful, with special focus on P0 regressions and architecture-contract assertions.
4. Run the first API/UI test pass and write durable findings under this task's research/artifact notes without storing secrets.
5. Fix grouped failures in backend, frontend, or tests as needed.
6. Verify with targeted unit/static tests, then rerun the full real WSL system test plan.
7. Complete Trellis check/spec-update/commit steps.

## Decision (ADR-lite)

**Context**: The user requested real end-to-end testing and bug fixing until the supplied plan passes, not just a targeted unit-test repair.

**Decision**: Treat the supplied markdown test plan as the executable oracle. Build temporary WSL evidence and scripts outside the repository where possible, while only committing product code, tests, specs, and Trellis task metadata.

**Consequences**: This is intentionally broad and may take multiple test/fix cycles. Evidence artifacts stay in the WSL temp run directory and are summarized in task notes/final output instead of being committed.

## Out of Scope

* Committing real request-log exports, browser storage state, generated images, screenshots, or provider credentials.
* Changing external provider behavior or bypassing upstream incompatibilities beyond producing controlled local errors.
* Creating unrelated UI redesigns or broad refactors not required to pass the test plan.

## Technical Notes

* Authoritative plan: `LOCAL_STUDIO_WEB_REAL_SYSTEM_TEST_PLAN.md`.
* Repository workflow: `develop_workflow.txt`.
* Project instructions: `AGENTS.md`.
* Spec index: `.trellis/spec/backend/index.md`.
* Relevant code discovered so far: `src/aistudio_api/api/routes_local_studio.py`, `src/aistudio_api/infrastructure/local_studio.py`, `src/aistudio_api/api/routes_request_logs.py`, `src/aistudio_api/static/`.
* User confirmation: the initial request explicitly directs execution through testing, bug fixing, retesting, and workflow closeout; no blocking requirement question is open.
