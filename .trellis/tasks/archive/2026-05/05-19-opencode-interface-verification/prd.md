# Verify opencode interfaces via WSL deployment

## Goal

Deploy the current project in a temporary WSL environment using real AI Studio account credentials, then verify from the Windows host that the exposed API works for OpenCode and the documented compatibility surfaces.

## What I already know

* The repository exposes OpenAI-compatible `/v1/chat/completions`, OpenAI Responses `/v1/responses`, Anthropic Messages `/v1/messages`, and Gemini-native `/v1beta/...` routes.
* README documents OpenCode as a custom OpenAI-compatible provider using `/v1/chat/completions`.
* README documents `web_search`, `web_search_preview`, and `browser_search` mapping to AI Studio Google Search.
* Real credentials live in WSL under `/home/bamboo/aistudio-api/data/accounts`.
* Existing OpenCode global config lives under Windows user paths such as `C:\Users\bamboo\.config\opencode` and must not be modified.

## Requirements

* Work from a clean branch based on latest `origin/master`.
* Deploy in WSL under a temporary directory, not by mutating the Windows workspace runtime data.
* Point `AISTUDIO_ACCOUNTS_DIR` at the real WSL credentials directory for the deployed service.
* Verify from Windows host, not only inside WSL.
* Cover these surfaces with live requests:
  * OpenAI Chat Completions compatibility.
  * OpenAI Responses API compatibility.
  * Gemini-native `generateContent` compatibility.
  * Anthropic/Claude Messages compatibility.
  * Web search tool mapping.
  * OpenCode custom OpenAI-compatible provider path.
* Do not modify existing OpenCode global config, auth, cache, state, or data directories.

## Acceptance Criteria

* [x] WSL service starts successfully from a temporary deployment directory.
* [x] Windows can reach the WSL service through `localhost` or the selected host/port.
* [x] `/health` and `/v1/models` return successful responses.
* [x] OpenAI Chat Completions request returns text or valid streaming deltas.
* [x] `/v1/responses` request returns a valid Responses object.
* [x] Gemini-native `:generateContent` request returns candidates text.
* [x] `/v1/messages` request returns Anthropic Messages-compatible content.
* [x] A search-tool request using `web_search` succeeds and returns grounded text or a valid compatible response.
* [x] `opencode run` succeeds using an isolated temporary OpenCode config/provider.
* [x] No files under the existing global OpenCode config/data/state/cache paths are intentionally modified.

## Out of Scope

* Permanent changes to the user's OpenCode configuration.
* Adding or changing AI Studio account credentials.
* Creating persistent deployment services or startup scripts unless needed to fix a discovered defect.

## Technical Notes

* OpenCode temporary config research: `research/opencode-temporary-config.md`.
* Live verification results: `research/verification-report.md`.
* Relevant backend spec: `.trellis/spec/backend/index.md` and quality guidelines referenced by that index.
