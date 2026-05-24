# Streaming Reasoning Display Test Results

## Observation

The user reported that reasoning was not visible in the Local Studio UI. The currently visible browser state had `Reasoning > Effort` set to `off`, so that specific conversation is not expected to show a thinking block. However, previous real WSL evidence showed a real coverage gap: high-reasoning Local Studio Responses stream completed successfully but recorded `assistant_has_thinking: false`, while the equivalent non-stream case preserved `thinking`.

## Fix

Root cause:

* Local Studio recognized internal compatibility stream events such as `response.reasoning.delta`, but did not recognize OpenAI Responses reasoning-summary stream events such as `response.reasoning_summary_text.delta` / `response.reasoning_summary_text.done`, nor completed reasoning output items emitted as `response.output_item.done`.
* The frontend already renders a reasoning block when the final assistant message has a non-empty `thinking` field, so the missing UI block was downstream of missing stream parsing/persistence.

Change:

* `parse_responses_stream_event(...)` now treats reasoning text and reasoning summary stream events as `thinking`.
* Reasoning `response.output_item.done` / `response.output_item.added` payloads and reasoning summary parts are parsed through the existing Responses output parser.
* Unit coverage now asserts both parser extraction and full Local Studio stream persistence into the completed conversation.
* `LOCAL_STUDIO_WEB_REAL_SYSTEM_TEST_PLAN.md` now hard-fails the earlier coverage gap: collected oracle fields such as `assistant_has_thinking`, `thinking_length`, and `reasoning_summary_visible` must be wired into failures instead of only written to artifacts.
* `research/system-test-plan-gap-audit.md` records the broader runner/oracle alignment risks found during review.

## Verification

Focused local checks:

* `pytest tests/unit/test_local_studio.py -q` -> 39 passed.
* `pytest tests/unit/test_local_studio.py tests/unit/test_static_frontend_capabilities.py -q` -> 54 passed.
* Python syntax/diagnostics for `research/run_streaming_reasoning_smoke.py` -> passed.

Full local checks:

* `pytest` -> 353 passed.
* `node --check src/aistudio_api/static/app.js` -> passed.
* `git diff --check` -> passed.

Real WSL targeted smoke:

* Run root: `/home/bamboo/aistudio-api-system-test-20260524-211242`.
* Server: `http://127.0.0.1:18082` with isolated Local Studio/request-log/generated-image/image-session directories.
* Command: `python .trellis/tasks/05-24-05-24-local-studio-streaming-reasoning-display/research/run_streaming_reasoning_smoke.py --base-url http://127.0.0.1:18082 --run-root /home/bamboo/aistudio-api-system-test-20260524-211242`.
* Result: no failures; API completed conversation had `thinking_length: 1360`; browser UI showed `Reasoning summary`.

Artifact handling:

* Raw WSL artifacts remain under the run root and are not committed.
* The smoke script records only metadata and thinking length, not token values or full provider output.