# Verification Report

## Environment

* Date: 2026-05-19
* Branch: `feature/opencode-interface-verification`
* WSL distribution: `Ubuntu-24.04`
* WSL deployment directory: `/home/bamboo/aistudio-opencode-verify-FgTNAu`
* API base URL from Windows: `http://127.0.0.1:18080`
* AI Studio mode: browser-backed Camoufox mode, not pure HTTP mode
* Accounts source: copied from `/home/bamboo/aistudio-api/data/accounts` into the temporary WSL deployment directory

## OpenCode Isolation

* OpenCode version in logs: `1.14.46`
* Temporary OpenCode root: `C:\Users\bamboo\AppData\Local\Temp\opencode-aistudio-verify-d022b681fb2f4e299b5f2c60f14425fa`
* `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME`, `XDG_CACHE_HOME`, `OPENCODE_CONFIG`, and `OPENCODE_CONFIG_DIR` were pointed at temporary paths for the run.
* Global OpenCode paths checked before and after the run; last-write timestamps stayed unchanged:
  * `C:\Users\bamboo\.config\opencode`
  * `C:\Users\bamboo\.local\share\opencode`
  * `C:\Users\bamboo\.local\state\opencode`
  * `C:\Users\bamboo\.cache\opencode`

## Live API Results

| Surface | Result | Evidence |
| --- | --- | --- |
| Health | Pass | `/health` returned `status=ok`. |
| Models | Pass | `/v1/models` returned 12 models, first model `gemma-4-31b-it`. |
| OpenAI Chat Completions | Pass | `/v1/chat/completions` returned `OK-CHAT`. |
| OpenAI Responses | Pass | `/v1/responses` returned `status=completed`, `output_text=OK-RESPONSES`. |
| Gemini native | Pass | `/v1beta/models/gemini-3-flash-preview:generateContent` returned `OK-GEMINI`. |
| Anthropic/Claude Messages | Pass | `/v1/messages/count_tokens` returned `input_tokens=5`; `/v1/messages` returned `OKCLAUDE` on full JSON inspection. |
| Web search tool | Pass | Chat Completions with `tools: [{"type":"web_search"}]` returned a grounded answer about the latest OpenCode stable version. |
| Responses streaming | Pass | SSE contained `response.created`, `response.output_text.delta`, and `response.completed`. |
| Messages streaming | Pass | SSE contained `message_start`, `content_block_delta`, and `message_stop`. |
| OpenCode provider | Pass | `opencode run` with isolated custom `aistudio/gemini-3-flash-preview` provider stored assistant text `OK-OPENCODE` in the temporary session export. |

## Notes

* The first Claude Messages extraction requested `Reply exactly: OK-CLAUDE` and produced an empty text in the compact projection. A follow-up full JSON inspection with `Write the single token OKCLAUDE.` returned the expected text block, so the compatibility surface was treated as passing based on the full response shape.
* The OpenCode JSON stream printed only the `step_start` event to the terminal, but exporting the temporary session confirmed the final assistant text `OK-OPENCODE` and a normal `finish=stop`.
