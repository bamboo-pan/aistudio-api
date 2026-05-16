# Playground Session History Management

## Goal

Improve the Playground chat workbench so conversations persist locally in the browser, old chats can be switched and restored, chat settings are available inline without the top-right settings dropdown, and each assistant response exposes practical usage telemetry including input tokens, output tokens, total tokens, cached token reads, and cache hit rate when the backend reports it.

## What I Already Know

* The current chat state lives only in `msgs`, `draft`, `chatFiles`, `cfg`, `model`, and `chatPreset` inside `src/aistudio_api/static/app.js`; refreshing loses conversations.
* Image generation already has local image history and backend image sessions; chat currently lacks equivalent session management.
* `src/aistudio_api/static/index.html` already duplicates much of the chat settings UI in the Playground side panel, while the topbar still has a Chat Settings gear/dropdown.
* The OpenAI-compatible response helper normalizes `usage` but currently drops `cached_tokens` parsed from AI Studio wire usage.
* Streaming chat sends a final usage SSE chunk when `include_usage` is true; the frontend currently ignores that usage chunk.

## Assumptions

* "本地存储" means browser `localStorage`, not a backend chat-session API.
* The MVP should avoid persisting large uploaded file data in long-term history; it can keep rendered user/assistant messages and lightweight attachment metadata where available.
* Because the project workflow says not to interrupt unless blocked, PRD confirmation will be recorded as override and implementation will proceed without a separate confirmation stop.

## Requirements

* Persist Playground chat sessions in browser localStorage.
* Support creating a new chat session, switching to previous sessions, restoring old messages/settings/model/preset, renaming by derived title, and deleting saved sessions.
* Save session changes automatically when messages, model, preset, or chat settings change.
* Move all chat settings out of the top-right gear dropdown and remove the Chat Settings button/dropdown from the topbar.
* Avoid duplicated settings controls after the redesign; keep model selection, presets, runtime switches, and numeric parameters in one coherent location.
* Display per-session and per-response token usage: input/prompt, output/completion, total, cached reads, and cache hit rate when available.
* For streaming responses, capture the final SSE usage chunk and attach usage to the assistant message after streaming completes.
* For non-streaming responses, attach `usage` from the JSON response to the assistant message immediately.
* Preserve current playground capabilities: file upload, prompt templates, markdown rendering, thinking block, copy message, model capability gating, and responsive layout.
* Preserve backend compatibility with existing clients while adding `cached_tokens` and prompt-token cache details to normalized usage.

## Acceptance Criteria

* [ ] Reloading the Playground restores the latest chat session from localStorage.
* [ ] Users can switch between saved chat sessions and see each session's old messages, model, preset, settings, and usage totals restored.
* [ ] Users can create a new chat and delete old local sessions.
* [ ] The top-right Chat Settings gear and dropdown are absent from the chat topbar.
* [ ] Chat setting controls are not duplicated between the input area and side panel.
* [ ] Assistant messages display token usage when usage data exists.
* [ ] A session-level usage panel shows accumulated input, output, total, cached tokens, and cache hit rate.
* [ ] Streaming and non-streaming chat both surface usage data when the backend sends it.
* [ ] Existing static frontend tests pass, and new/updated tests cover the session-history and usage UI strings.
* [ ] Backend response tests cover normalized cached-token usage.

## Definition of Done

* Tests added/updated for frontend static affordances and usage normalization.
* Relevant unit tests pass locally.
* Real WSL environment smoke test is run because this touches API/static playground behavior.
* No unrelated worktree changes are included in the work commit.

## Technical Approach

Implement browser-local chat sessions in `app.js` with a versioned localStorage key, bounded session list, active session id, helper methods for serialize/restore/touch/delete/new, and throttled-safe saves around message/settings mutations. Add usage helper methods that normalize OpenAI usage shapes and compute display rows/totals. Update `index.html` to add a local chat history panel and usage panels, remove the topbar settings dropdown, and consolidate settings in the existing Playground side panel. Update CSS for the new session list and usage rows. Update backend usage normalization so `cached_tokens` and `prompt_tokens_details.cached_tokens` survive to clients.

## Decision (ADR-lite)

**Context**: Chat history can be stored locally or implemented as a backend API similar to image sessions. The user explicitly asked for local storage, and chat messages may contain transient browser-only file data.

**Decision**: Use localStorage-only chat sessions for this task, with lightweight persisted message/session/settings snapshots and bounded history to avoid storage bloat.

**Consequences**: Sessions are per browser/profile and do not sync across machines. This keeps the feature low-risk and avoids introducing new backend persistence contracts. A future backend chat-history API can migrate from the versioned localStorage schema if needed.

## Out of Scope

* Cross-browser or server-side chat session sync.
* Export/import of chat sessions.
* Persisting large uploaded file binary data indefinitely beyond what current message rendering already holds.
* Token counting before sending a request.
* Changing account rotation or model gateway behavior.

## Technical Notes

* Likely frontend files: `src/aistudio_api/static/app.js`, `src/aistudio_api/static/index.html`, `src/aistudio_api/static/style.css`.
* Likely backend file: `src/aistudio_api/api/responses.py`.
* Static frontend tests live in `tests/unit/test_static_frontend_capabilities.py`.
* Backend usage response tests live in `tests/unit/test_api_responses.py`.
