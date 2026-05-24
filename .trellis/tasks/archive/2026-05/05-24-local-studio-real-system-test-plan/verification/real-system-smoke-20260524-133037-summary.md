# Local Studio Real System Smoke Summary

Run root: `/home/bamboo/aistudio-api-system-test-20260524-133037`
Base URL: `http://127.0.0.1:18080`
Credential sources: documented `AGENTS.md` WSL Google account directory and OpenAI-compatible key file. No secrets, cookies, generated images, raw request logs, or browser storage states are persisted here.

## Results

- `PASS` `BOOT-01` (api, 25ms): service healthy and request logs enabled.
- `PASS` `API-LS-01` (api, 56ms): Google Responses models loaded; selected `gemini-3.5-flash`.
- `FAIL` `API-LS-03` (api, 300038ms): Google basic non-stream chat returned controlled `HTTP 504: upstream request timed out after 300s`.
- `SKIP` `BUG-GEMINI-IMAGE-TOOL-01` (api, 0ms): blocked because Google AI Studio browser capture did not complete the basic chat path.
- `PASS` `API-LS-02` (api, 1226ms): OpenAI-compatible models loaded; selected `gpt-5.5`.
- `PASS` `BUG-OPENAI-SEARCH-STREAM-01` (api, 1237ms): OpenAI-compatible stream search path returned controlled SSE and server stayed healthy.
- `PASS` `BOOT-02` (ui, 7968ms): all primary routes loaded without console errors.
- `SKIP` `G-LS-01` (ui, 0ms): blocked because Google AI Studio browser capture did not complete the basic API path.
- `PASS` `O-LS-03` (ui, 7967ms): OpenAI-compatible UI search stream ended in controlled UI state.

## Bug Summary

- `BUG-OPENAI-SEARCH-STREAM-01`: fixed. Reproduction was an OpenAI-compatible Local Studio Responses stream with web search enabled returning an upstream stream error. Actual behavior before the fix was a server-side stream failure path that could expose `ResponseNotRead`; expected behavior is a controlled SSE error/completion and a healthy server. Verification: unit regression plus final real WSL smoke pass.
- `BUG-GEMINI-IMAGE-TOOL-01`: product-level conflict fixed, but end-to-end verification is blocked by the Google AI Studio browser capture path. The original conflict was Google rejecting built-in search combined with function tools; the fix splits the decision call when the provider requires it. Verification: unit regression passes. Real WSL smoke could not reach this path because `API-LS-03` basic Google browser capture timed out first.
- `API-LS-03`: remaining environment/provider blocker. Reproduction is Google Local Studio Responses non-stream chat with `gemini-3.5-flash` and a simple `回复 ok` prompt. Expected behavior is an assistant response; actual behavior is a controlled 504 after 300s. Server logs isolate it to AI Studio browser template capture timing out on `Page.goto("https://aistudio.google.com/", wait_until="commit")` after model listing succeeds. Direct isolated navigation and warmup probes succeeded earlier, so the unresolved failure is in the real browser-backed capture path under the WSL server flow, not in the OpenAI-compatible stream bug.

## Outcome

Independent P0 paths covered by this run: 5 pass, 1 fail, 2 skipped due to the same Google capture blocker. The server stayed healthy after the OpenAI-compatible stream search bug reproduction, and UI shell/OpenAI-compatible UI paths passed.
