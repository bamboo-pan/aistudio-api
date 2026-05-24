# System Test Plan Charter Results

## Change

Updated `LOCAL_STUDIO_WEB_REAL_SYSTEM_TEST_PLAN.md` so it explicitly acts as the global highest-level test charter for Local Studio/WebUI real system testing.

Added a dedicated `全局高风险遗漏类` section covering:

* UI visibility and state assertions.
* Provider and request-log signatures.
* Capability/process preservation for reasoning, tools, search, images, usage, and attachments.
* Recovery and repeated paths: refresh, rerun, cache hit, retry, delete/export.
* Cache isolation dimensions.
* `not_applicable` abuse prevention.
* Test harness oracle wiring gaps.
* Security and artifact boundaries.

## Verification

* `git diff --check` -> passed.
* `python ./.trellis/scripts/task.py validate 05-24-05-24-system-test-plan-charter` -> passed.
* Grep verification confirmed all high-risk omission classes are present in the top-level plan.

## Notes

This is documentation-only. No product code changed and no WSL real system retest is required for this task. Future system test execution must treat the top-level plan as the authority over task-local smoke scripts or reports.
