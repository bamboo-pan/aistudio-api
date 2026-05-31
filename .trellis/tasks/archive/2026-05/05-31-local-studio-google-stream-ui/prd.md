# Fix Local Studio Google AI Studio Streaming UI

## Goal

Fix the Local Studio Google AI Studio path so enabling Stream mode produces visibly incremental assistant output in the UI instead of rendering the response only after the upstream request completes.

## What I Already Know

- The observed failing path is Local Studio using the built-in Google AI Studio provider with Stream enabled.
- The screenshot shows the Responses interface with Web Search and the Gemini image tool enabled; the pending assistant card remains in the waiting state until the image result appears.
- The backend contract requires streamed Local Studio responses to emit incremental `local_studio.delta` events before the final `local_studio.completed` event.
- The static frontend already reads `response.body.getReader()` and appends `local_studio.delta.content` / `thinking` to the current assistant message.
- Google AI Studio provider requests are internally routed through the OpenAI-compatible `/v1` or Gemini `/v1beta` compatibility routes, so streaming can regress either in the compatibility stream bridge or in the Local Studio SSE bridge.

## Requirements

- Preserve Stream on/off behavior for Local Studio across built-in Google AI Studio and custom OpenAI-compatible providers.
- For Google AI Studio + Local Studio + Stream, emit at least one visible `local_studio.delta` event before `local_studio.completed` whenever upstream text, reasoning, or tool-selection chunks arrive incrementally.
- For Responses image-tool streams, show tool-selection progress in the assistant stream before the generated image completion arrives.
- Keep final conversation persistence unchanged: the completed event must still contain the saved assistant message, usage, reasoning, images, and errors where applicable.
- Do not introduce or revive Local Studio final-result caching.
- Do not persist runtime credentials or tokens in task artifacts, tests, or conversation files.

## Acceptance Criteria

- [ ] Unit coverage proves Local Studio streams Google-provider Responses text/tool chunks as incremental `local_studio.delta` events before `local_studio.completed`.
- [ ] Unit/static checks still pass for Local Studio stream and frontend syntax.
- [ ] Real API smoke in WSL verifies a Local Studio Google AI Studio streamed request receives a delta before completion.
- [ ] Browser UI smoke verifies the Local Studio streamed assistant message updates before final completion.

## Definition of Done

- Focused code changes only in the streaming bridge/parser/frontend state path as needed.
- Relevant unit tests pass.
- `node --check src/aistudio_api/static/app.js` passes if the static app is edited.
- Required WSL real API and browser UI tests pass for this bug path.
- Task files under this directory are committed with the code changes.

## Verification

- Focused Local Studio unit suite: `41 passed`.
- Related Local Studio / Responses / static contract suite: `106 passed`.
- Full unit suite: `372 passed`.
- `git diff --check` passed.
- VS Code diagnostics found no errors in the changed Python files.
- WSL real API + browser UI smoke passed from `/home/bamboo/aistudio-api-google-stream-ui-20260531-111545`; API verified `local_studio.delta.thinking` before `local_studio.completed`, and Playwright verified Local Studio UI thinking updated while the pending indicator was still visible.

## Bug Analysis

### 1. Root Cause Category

- **Category**: D - Test Coverage Gap, plus B - Cross-Layer Contract.
- **Specific Cause**: Prior streaming verification covered ordinary text deltas but not Responses image-tool streams. The compatibility layer emitted `function_call` tool-selection events, but the Local Studio parser only turned text/reasoning/image candidates into visible deltas, so the UI looked idle until final image completion.

### 2. Why The Earlier Fix Missed This

- The API/UI smoke from the previous stream task validated incremental text with the image tool enabled but explicitly told the model not to generate an image.
- The image-tool smoke validated final image generation and asset rendering, but did not assert any pre-completion progress event for the tool path.

### 3. Prevention Mechanisms

| Priority | Mechanism | Specific Action | Status |
|----------|-----------|-----------------|--------|
| P0 | Unit coverage | Assert Responses `function_call` output items become Local Studio `local_studio.delta.thinking` before completion. | DONE |
| P0 | Real UI coverage | Assert browser state shows tool progress while the pending indicator is still visible. | DONE |
| P1 | Spec contract | Document image-tool function-call progress as part of the Local Studio stream contract. | DONE |

### 4. Systematic Expansion

- **Similar Issues**: Any provider stream event that is not plain text or reasoning can be silently ignored by Local Studio unless mapped into visible progress, persisted state, or an explicit not-applicable state.
- **Design Improvement**: Treat stream parser output as a UI-state contract, not just a final persistence parser.
- **Process Improvement**: Real stream smokes should check both normal text streams and tool-selected streams when a tool surface is involved.

### 5. Knowledge Capture

- Updated `.trellis/spec/backend/quality-guidelines.md` with the image-tool stream progress contract and required API/UI real smoke assertions.

## Technical Approach

Trace the Local Studio stream path from `/api/local-studio/chat` through the internal Google provider compatibility endpoint and the static `sendLocalStudioStream` reader. Fix the first layer that buffers or suppresses incremental text/reasoning/tool events, preferring a backend fix if the frontend reader already receives only final data.

## Out of Scope

- Redesigning Local Studio UI layout.
- Changing model/provider selection semantics.
- Adding new cache behavior.
- Broad refactors of the OpenAI/Gemini/Claude compatibility layers.

## Technical Notes

- Relevant spec: `.trellis/spec/backend/quality-guidelines.md`, scenario "Local Studio API, Provider Profiles, No Result Cache, Interface Modes, and Tools".
- Relevant frontend file: `src/aistudio_api/static/app.js` currently has `sendLocalStudioStream(...)` with `ReadableStream` parsing.
- Relevant backend files: `src/aistudio_api/api/routes_local_studio.py`, `src/aistudio_api/infrastructure/local_studio.py`, and `src/aistudio_api/application/api_service.py`.