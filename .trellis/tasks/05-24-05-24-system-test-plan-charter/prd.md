# Harden System Test Plan Charter

## Goal

Make `LOCAL_STUDIO_WEB_REAL_SYSTEM_TEST_PLAN.md` the global highest-level test charter for Local Studio and shared WebUI modules by explicitly capturing high-risk omission classes, oracle enforcement rules, and plan/script alignment requirements.

## What I Already Know

* The user wants this document to act as the global top-level testing authority.
* The previous reasoning bug showed a plan-script gap: `assistant_has_thinking=false` was recorded but not failed.
* The current plan already has some hard gates for reasoning, `contains_*` error signatures, `assistant_has_*` fields, and `not_applicable` handling.
* The high-risk omission categories still need to be visible as first-class global plan content, not only in task-local research notes.

## Requirements

* Add a clear hierarchy statement: this plan is the highest test oracle for Local Studio/system testing and scripts cannot weaken it.
* Add a dedicated high-risk omission class section.
* Cover UI visibility, provider/request-log signatures, capability preservation, recovery paths, `not_applicable` abuse, and harness pass/fail wiring.
* Keep the change documentation-only and scoped to the top-level test plan plus Trellis task metadata.

## Acceptance Criteria

* [ ] The top-level test plan explicitly names all high-risk omission classes.
* [ ] The plan states that collected oracle fields must be mapped to pass/fail/not_applicable.
* [ ] The plan states that task-local scripts cannot be the final authority if they diverge from the plan.
* [ ] Markdown/diff checks pass.

## Definition of Done

* `git diff --check` passes.
* Trellis task metadata is committed with the documentation update.
* No real test artifacts, request-log exports, screenshots, tokens, or generated images are committed.

## Out of Scope

* Building a permanent `tests/system/` runner in this task.
* Running full WSL system tests for this documentation-only change.
* Changing product code.

## Technical Notes

* Main file: `LOCAL_STUDIO_WEB_REAL_SYSTEM_TEST_PLAN.md`.
* Related evidence: `.trellis/tasks/archive/2026-05/05-24-05-24-local-studio-streaming-reasoning-display/research/system-test-plan-gap-audit.md`.
