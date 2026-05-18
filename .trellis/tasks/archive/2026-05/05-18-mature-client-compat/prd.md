# Mature client compatibility support

## Goal

Improve the API compatibility layers so common OpenAI-compatible, Responses, Gemini-native, and Anthropic/Claude clients can use this project in practical coding/chat workflows. The first mature-support pass should prioritize real client usability for CherryStudio search, OpenCode, Claude Code gateway basics, and Codex-style Responses streaming while staying honest about unsupported hosted-provider-only features.

## What I Already Know

- The repo exposes `/v1/chat/completions`, `/v1/responses`, `/v1/messages`, `/v1/models`, `/v1/images/generations`, and Gemini-native `/v1beta` routes.
- OpenAI Chat Completions is currently the strongest compatibility path: streaming, function-call deltas, image/file input, structured output, thinking, and project-specific `grounding` exist.
- OpenAI Responses currently supports simple non-streaming requests, `text.format/json_schema`, function tool declarations, function-call output items, and thinking control.
- Anthropic Messages currently supports simple non-streaming messages, system text, Claude-style tool declarations, and `tool_use` output blocks.
- Gemini-native supports generate, stream, countTokens, `googleSearch`/`googleSearchRetrieval`, `codeExecution`, `functionDeclarations`, inlineData, and generationConfig validation.
- CherryStudio search cannot use the current server because OpenAI `tools` only accepts `type=function`; standard web search tool shapes are not mapped to Google Search grounding.

## Research References

- `research/client-protocol-compatibility.md` - summarizes OpenAI web search, Anthropic Messages streaming/tooling, Claude Code gateway requirements, and OpenCode provider conventions.

## Assumptions

- The requested "mature support" means mature enough for real client workflows, not bit-for-bit full OpenAI/Anthropic hosted API parity.
- Backwards compatibility with existing project-specific `grounding`, `thinking`, and Gemini-native behavior must be preserved.
- The browser-backed AI Studio gateway remains the upstream execution engine; this task should not add a separate search provider or external API key dependency.
- If a client sends a search tool shape, enabling AI Studio Google Search is preferable to failing with unsupported tool type even if citation metadata cannot be fully reproduced.

## Requirements

1. OpenAI-compatible Chat Completions must accept standard search tool shapes in addition to `grounding: true`.
2. `/v1/responses` must accept standard search tool shapes and support a practical streaming subset for text and function-call output.
3. `/v1/messages` must accept Anthropic web search tool shapes and support Anthropic-style streaming events for text, thinking, and tool_use output.
4. Gemini-native behavior must keep existing `googleSearch`/`googleSearchRetrieval`, `functionDeclarations`, and streaming support working.
5. Claude Code gateway basics must improve by adding Anthropic-style token counting for messages; model discovery should be considered without breaking OpenAI `/v1/models` clients.
6. Error shapes must remain client-appropriate: OpenAI-compatible routes return OpenAI `{error: ...}` shape, Gemini routes return current Gemini-style details/SSE errors, and Anthropic stream errors use Anthropic-style `event: error` where practical.
7. Documentation must describe which client path to use for CherryStudio, OpenCode, Claude Code, and Codex after the changes.

## Acceptance Criteria

- [ ] Unit tests cover OpenAI Chat Completions accepting `web_search`, `web_search_preview`, and at least one common alias as Google Search grounding.
- [ ] Unit tests cover `/v1/responses` non-streaming and streaming search/tool behavior.
- [ ] Unit tests cover `/v1/messages` non-streaming and streaming Anthropic text/tool_use behavior.
- [ ] Unit tests cover `/v1/messages/count_tokens` returning `input_tokens`.
- [ ] Existing Gemini-native tests still pass.
- [ ] README documents client-specific support and limitations.
- [ ] WSL real environment test passes for affected API behavior using real account credentials, because this task changes API/tool/gateway behavior.

## Definition of Done

- Tests added/updated for each changed compatibility surface.
- Relevant unit tests and broader affected tests pass locally.
- Real WSL browser-backed smoke tests pass for search/tool-compatible requests.
- Documentation updated for real client usage and known limitations.
- Task files under `.trellis/tasks/05-18-mature-client-compat/` are committed with the implementation.

## Out of Scope

- Full OpenAI Responses parity for background mode, hosted file_search, computer_use, encrypted reasoning payloads, or provider-managed conversation state.
- Full Anthropic parity for prompt caching semantics, beta feature forwarding, server-side bash/text-editor tools, or exact Claude thinking signatures.
- Returning real OpenAI/Anthropic citation metadata when AI Studio only returns textual grounded output.
- Adding new external hosted search providers.

## Technical Notes

- Likely implementation files: `src/aistudio_api/api/schemas.py`, `src/aistudio_api/application/chat_service.py`, `src/aistudio_api/application/api_service.py`, `src/aistudio_api/api/routes_openai.py`, `src/aistudio_api/api/responses.py`, README files, and compatibility tests.
- Existing tests to extend: `tests/unit/test_openai_compatibility.py`, `tests/unit/test_gemini_request_normalization.py`, `tests/unit/test_gemini_native_routes.py`, `tests/unit/test_api_responses.py`, and streaming tests.
- The internal Google Search wire template is `TOOLS_TEMPLATES["google_search"]`.
- Existing OpenAI Chat validation currently tracks search only through `req.grounding`; search tools need to flow into capability validation.
- Existing `/v1/responses` and `/v1/messages` reject `stream: true`; this task should replace that with well-formed SSE subset support.
