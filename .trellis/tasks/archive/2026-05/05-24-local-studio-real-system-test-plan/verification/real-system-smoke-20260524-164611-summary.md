# Local Studio Real System Smoke Summary

Run root: `/home/bamboo/aistudio-api-system-test-20260524-164611`
Base URL: `http://127.0.0.1:18081`
Credential sources: documented `AGENTS.md` WSL Google account directory and OpenAI-compatible key file. No secrets, cookies, generated images, raw request logs, or browser storage states are persisted here.

## Results

- `PASS` `BOOT-01` (api, 18ms): service healthy and request logs enabled.
- `PASS` `API-LS-01` (api, 134ms): Google Responses models loaded; selected `gemini-3.5-flash`.
- `PASS` `API-LS-03` (api, 112283ms): Google basic non-stream chat completed.
- `PASS` `BUG-GEMINI-IMAGE-TOOL-01` (api, 51127ms): Gemini search + image-tool stream path completed without the `include_server_side_tool_invocations` error.
- `PASS` `API-LS-02` (api, 2190ms): OpenAI-compatible models loaded; selected `gpt-5.5`.
- `PASS` `BUG-OPENAI-SEARCH-STREAM-01` (api, 2917ms): OpenAI-compatible stream search path returned controlled SSE and server stayed healthy.
- `PASS` `BOOT-02` (ui, 9537ms): all primary routes loaded without console errors.
- `PASS` `G-LS-01` (ui, 12473ms): Google Local Studio UI loaded models and sent a message.
- `PASS` `O-LS-03` (ui, 9960ms): OpenAI-compatible UI search stream ended in controlled UI state.

## Bug Summary

- No new P0 bugs were found in this run.
- `BUG-GEMINI-IMAGE-TOOL-01`: verified green in real WSL API path after the previous fix. The Google provider Local Studio Responses path with search and image tool enabled completed without the historical tool-config error.
- `BUG-OPENAI-SEARCH-STREAM-01`: verified green in real WSL API and UI paths. The OpenAI-compatible stream search path returned a controlled stream result/error state and the server remained healthy.
- The previous Google AI Studio browser-capture blocker did not reproduce in this run; `API-LS-03` and `G-LS-01` both passed.

## Outcome

All P0 real-system API/UI smoke paths executed by `run_real_system_smoke.sh` passed. No raw server logs, request-log exports, generated images, token values, cookies, or storage states were committed.
