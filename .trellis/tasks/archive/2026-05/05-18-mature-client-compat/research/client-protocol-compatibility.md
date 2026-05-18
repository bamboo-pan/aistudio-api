# Client Protocol Compatibility Research

## Sources Consulted

- OpenAI web search tool guide: Responses API uses `tools: [{"type":"web_search"}]` for current integrations; legacy `web_search_preview` remains accepted. Search output may include `web_search_call` items and message annotations.
- Anthropic Messages API docs: Messages content supports `text`, `tool_use`, `tool_result`, images/documents, usage mapping, and `tool_choice`.
- Anthropic Messages streaming docs: SSE flow is `message_start`, content block start/delta/stop, `message_delta`, and `message_stop`; tool-use deltas use `input_json_delta` partial JSON.
- Claude Code LLM gateway docs: Anthropic-compatible gateways must expose `/v1/messages` and `/v1/messages/count_tokens`, forward `anthropic-beta` and `anthropic-version`, and support gateway model discovery through `/v1/models` for Claude-like model ids.
- OpenCode provider docs: custom OpenAI-compatible providers can use `@ai-sdk/openai-compatible` for `/v1/chat/completions`; models using `/v1/responses` should use `@ai-sdk/openai`.

## Current Repo Fit

- The strongest current path for OpenCode and CherryStudio is OpenAI Chat Completions because this repo already supports stream chunks, image/file input, structured output, and function tool-call deltas.
- The strongest current path for Gemini SDK users is Gemini native `/v1beta`, because it already exposes generate, stream, countTokens, inlineData, functionDeclarations, and Google Search.
- The current Claude Code path is incomplete because `/v1/messages` rejects `stream: true`, lacks `/v1/messages/count_tokens`, and does not expose Claude-compatible `/v1/models` discovery.
- The current Codex/Responses path is incomplete because `/v1/responses` rejects `stream: true` and does not emit Responses event streams.

## Recommended Implementation Scope

1. Normalize tool requests across OpenAI Chat, Responses, and Anthropic Messages:
   - Accept OpenAI `web_search`, `web_search_preview`, `web_search_preview_*`, and common `browser_search`/`search` aliases as Google Search grounding.
   - Preserve function declarations and reject only truly unsupported non-search tool types.
   - Map Anthropic web search tool types such as `web_search_20250305` to Google Search grounding.

2. Add mature streaming subsets:
   - `/v1/responses` should stream a minimal but well-formed Responses SSE sequence for text and function-call output, using existing AI Studio stream events.
   - `/v1/messages` should stream Anthropic-style SSE events for text, thinking, and tool_use blocks.

3. Add Claude Code gateway essentials:
   - `/v1/messages/count_tokens` should return Anthropic-style `input_tokens` using the existing token estimator.
   - `/v1/models` should be able to expose model entries that Claude Code can discover when a Claude-compatible model alias is configured.

4. Document practical client setup:
   - CherryStudio/OpenAI-compatible clients: use `/v1`, Chat Completions; search works through standard web search tools or project `grounding`.
   - OpenCode: prefer `@ai-sdk/openai-compatible` against `/v1` for chat-completions compatibility.
   - Claude Code: use Anthropic `/v1/messages` after streaming/count_tokens support lands; model aliases may be needed.
   - Codex: Responses streaming support is a compatibility subset, not full OpenAI hosted tool/background/state parity.

## Explicit Non-Goals

- Do not implement real hosted OpenAI web search result objects or citations beyond what AI Studio returns in text.
- Do not implement OpenAI background Responses, full conversation-state APIs, hosted file_search/computer_use/code_interpreter, or encrypted reasoning payloads.
- Do not implement Anthropic server-side tools beyond mapping web search to AI Studio Google Search.
- Do not change gateway replay contracts unless tests show it is required.
