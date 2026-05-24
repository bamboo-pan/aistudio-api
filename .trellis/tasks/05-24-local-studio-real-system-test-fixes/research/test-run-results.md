# Real System Test Run Results

## Initial Run

Run root: `/home/bamboo/aistudio-api-system-test-20260524-194000`

Summary:

* BOOT/API smoke passed: Local Studio health, request-log status, `/v1/models`, and `/v1beta/models` returned 200.
* Browser UI smoke passed after script wait-condition adjustment: `#studio`, `#chat`, `#images`, `#requests`, `#accounts`; Local Studio Google streamed send completed with no console or page errors.
* Focused smoke passed: 16 API cases, 5 UI routes, request-log lifecycle phases present and OpenAI token redacted.
* Extended matrix initially failed because request logs contained `Please enable tool_config.include_server_side_tool_invocations to use Built-in tools with Function calling.` for Google AI Studio Responses with search plus image tool.

Bug found:

* `BUG-GEMINI-IMAGE-TOOL-01`: the implementation recovered from the upstream 400 by retrying a search-only decision prompt, but the first failing upstream call was still recorded in request logs. The plan requires the upstream response not to contain the `include_server_side_tool_invocations` error, so this was a real P0 regression.

## Fix

Root cause:

* `_complete_responses_optional_image_generation(...)` first sent Google built-in search (`web_search_preview`) together with the converted `image_generation` function tool. AI Studio rejects built-in tools with function calling unless a server-side invocation flag is enabled. The retry path hid the error from the final user-visible response but could not remove the failed upstream lifecycle entry from request logs.

Change:

* For payloads that include search and image generation, the decision request now starts directly with the search-only image decision prompt. The allowed `image_generation` tool name is retained locally so the text protocol response can still be parsed and followed by actual image generation.
* The unit test now asserts only one decision chat request is made and that it contains `web_search_preview` without the `image_generation` function tool.

## Final Run

Run root: `/home/bamboo/aistudio-api-system-test-20260524-201147`

Smoke results:

* `artifacts/summary.md`: 16 API cases, 5 UI routes, no failures.
* `artifacts/api-results.json`: Google optional tools, OpenAI-compatible search stream, OpenAI-compatible reasoning stream/non-stream, cache, health, and request-log checks passed.
* `artifacts/ui-results.json`: 5 routes loaded, no console errors, no page errors, Local Studio send completed, no pending residue.
* `artifacts/architecture-contract-results.json`: provider-aware search tools, request-log lifecycle, and frontend state-machine assertions passed.

Extended matrix results:

* `artifacts/matrix-summary.json`: 51 cases, no failures.
* Cache isolation passed: first miss, repeat hit, namespace miss, search miss, reasoning miss, repeat hit.
* Request logs passed: 90 groups, token redacted, Google `web_search_preview` seen, OpenAI-compatible `web_search` seen, no `ResponseNotRead`, no ASGI exception, no `include_server_side_tool_invocations`, no `Unsupported tool type: web_search_preview`.
* `BUG-GEMINI-IMAGE-TOOL-01` passed: status 200, assistant content `Generated image`, one image saved, no config error signature.
* Base image generation passed: one image generated and its local asset returned status 200 with image MIME.
* OpenAI-compatible Gemini interface negative path remained controlled: non-stream returned 404 from upstream, stream returned a completed Local Studio SSE with an assistant error and no backend exception.

Local automated verification:

* `pytest tests/unit/test_api_responses.py tests/unit/test_local_studio.py tests/unit/test_openai_compatibility.py` -> 83 passed.
* `pytest` -> 351 passed.
* `node --check src/aistudio_api/static/app.js` -> passed.
* VS Code diagnostics for changed Python files -> no errors.

Artifact handling:

* Raw screenshots, generated images, request-log exports, and server logs remain in the WSL temp run directories and are not committed.
* Secret redaction was checked by the smoke and matrix scripts.