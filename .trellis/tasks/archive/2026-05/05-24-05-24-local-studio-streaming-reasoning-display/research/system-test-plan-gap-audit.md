# System Test Plan Gap Audit

## What Happened

The top-level real system test plan already described the general contract that Responses reasoning must not be lost across API, UI, conversation persistence, refresh recovery, and request logs. However, the previous real smoke runner recorded `assistant_has_thinking: false` for `O-LS-06-reasoning-stream` without turning that observation into a test failure.

This means the product bug was not caused by a missing high-level requirement alone. It was caused by an oracle-enforcement gap: the script collected the right symptom but treated it as informational.

## Plan Updates Made

`LOCAL_STUDIO_WEB_REAL_SYSTEM_TEST_PLAN.md` now explicitly requires:

* Streaming reasoning parser coverage for `response.reasoning.*`, `response.reasoning_text.*`, `response.reasoning_summary_text.*`, `response.reasoning_summary_part.*`, and reasoning `response.output_item.*` events.
* High-reasoning stream cases to hard-fail if the final `local_studio.completed` assistant message has empty `thinking` when upstream returned reasoning.
* Browser UI and refresh recovery checks to hard-fail if `Reasoning summary` or an equivalent visible/auditable entry is missing when reasoning was returned.
* Any collected oracle field such as `assistant_has_thinking`, `thinking_length`, `reasoning_summary_visible`, `contains_*_error`, or `secret_redacted` to be wired into pass/fail logic unless explicitly marked `not_applicable` with a reason.
* A plan-script alignment audit after each system test run.

## Similar Remaining Risk Classes

The same pattern can recur anywhere a runner writes useful metadata but does not fail on it. Highest-risk fields and contracts:

* UI visibility fields: `*_visible`, `has_*`, `completed`, pending-state booleans, console/page errors.
* Provider/request-log signatures: `contains_*`, provider-specific tool names, upstream request body checks, secret redaction booleans.
* Capability preservation fields: reasoning/tool/search/image details, usage, cache markers, attachments, generated asset URL reachability.
* Recovery paths: refresh restore, rerun, cache hit, error retry, and delete/export lifecycle checks.
* `not_applicable` branches that are used because a provider/model did not expose a capability; these need explicit reason strings and must not hide skipped positive coverage.

## Structural Gap

The current repository has task-local smoke scripts under `.trellis/tasks/.../research/`, but no maintained first-class system-test runner under `tests/system/` or an equivalent stable path. That makes it easy for future sessions to copy an older task script that records fields without enforcing all plan oracles.

Recommended follow-up:

* Promote the real system smoke/matrix runners into a maintained system-test location.
* Add an oracle helper that requires every collected `expected`, `contains_*`, `*_visible`, `assistant_has_*`, `secret_redacted`, and `not_applicable` field to be classified as pass/fail/not_applicable with a reason.
* Keep task-local scripts only for experiment-specific probes, not as the authoritative system-test implementation.
