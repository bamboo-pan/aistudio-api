# Local Studio Image Tool Provider Differentiation

## Goal

Make Local Studio image tool behavior provider-aware so Google AI Studio/Gemini and custom OpenAI-compatible providers expose and execute the image generation features they actually support. Fix the current Gemini image tool flow issues observed in request logs: duplicate image display, hidden intermediate/tool details, OpenAI-branded controls shown for Gemini, and mismatched image model/size/format options.

## What I Already Know

- The current Local Studio sidebar always labels the Responses image tool as `gpt-image-2`, even when the active provider is Google AI Studio.
- `src/aistudio_api/static/app.js` currently stores a single image tool setting set: size, quality, background, format, compression.
- `src/aistudio_api/static/index.html` renders one static Image Tool panel with OpenAI-oriented wording and controls.
- `src/aistudio_api/infrastructure/local_studio.py` builds OpenAI Responses payloads and currently emits the OpenAI image generation tool shape.
- `src/aistudio_api/application/api_service.py` adapts Responses image_generation for Google AI Studio by using `DEFAULT_IMAGE_MODEL`, currently `gemini-3.1-flash-image-preview`.
- `src/aistudio_api/domain/model_capabilities.py` already knows two Gemini image models: `gemini-3.1-flash-image-preview` and `gemini-3-pro-image-preview`, with different supported size maps.
- The exported request log showed one user message (`做成图片`) causing an outer Local Studio request, an inner `/v1/responses` request, a Gemini text call, then a Gemini image call.
- The exported request log showed the actual image was one 1024x1024 JPEG, but the final Local Studio UI displayed two image entries.
- The exported request log showed intermediate thinking/text/tool details were not surfaced in the final Local Studio UI.

## Requirements

- Local Studio must differentiate Google AI Studio/Gemini image tool controls from custom OpenAI-compatible image tool controls.
- Gemini image tool controls must offer a selectable Gemini image model instead of hard-coding the default Flash image model.
- Gemini image model selection must dynamically determine supported size options and defaults.
- OpenAI-compatible image tool controls must continue to use OpenAI image model/parameter semantics and not inherit Gemini-only constraints.
- Unsupported parameters for the selected provider/model must not be presented as active controls or must be omitted from the request payload.
- The request payload must include enough image tool metadata for the backend to choose the intended image model and parameters.
- Google AI Studio Responses image generation must use the selected Gemini image model when the image tool is invoked.
- The Local Studio UI must show image tool progress/intermediate details enough for users to see that a tool call is happening and which model is used.
- The Local Studio UI must preserve/display available thinking or tool trace details instead of silently collapsing the process to only `Generated image`.
- Generated images from a single image call must be deduplicated in the persisted conversation and rendered UI.
- Responses image generation streaming must avoid avoidable duplicate large image payloads where practical.
- Existing Local Studio text chat, provider selection, cache behavior, and custom OpenAI provider behavior must continue to work.
- Existing base modules must remain independently usable and must not be absorbed into Local Studio as their only access path.
- The existing top-level Playground, Image Generation, Request Logs, and Account Management pages must continue to work normally after Google AI Studio is also exposed as a Local Studio provider.
- Local Studio may wrap or reuse the same underlying Google AI Studio capability lines, but this reuse must not change the standalone behavior of those base modules.
- Google AI Studio base capabilities are separated into standalone lines: chat + search, chat + image generation, and account management.
- Request management is a shared service layer for all modules, including Playground, Image Generation, Account Management, and Local Studio.
- In Local Studio, tool toggles represent optional capabilities that the active model may use when needed; enabling a tool must not force every request to call that tool.
- When the default Gemini provider is selected and neither search nor image generation is enabled, Local Studio must behave as a normal chat-only conversation.
- When the default Gemini provider has search and/or image generation enabled, Local Studio must support multi-capability conversations where the model can still answer normally if no tool is needed, or call the enabled search/image tool only when the request calls for it.
- Custom OpenAI-compatible providers follow the same optional-tool semantics: Local Studio should include the enabled search/image tool definitions in the request, and the provider/model decides whether to call them.

## Acceptance Criteria

- [ ] With Google AI Studio selected, the Local Studio image tool panel shows Gemini image tool identity and Gemini image model selection.
- [ ] Selecting `gemini-3.1-flash-image-preview` exposes only its supported size set.
- [ ] Selecting `gemini-3-pro-image-preview` exposes the Pro image size set, including higher resolution options.
- [ ] With a custom OpenAI provider selected, the image tool panel remains OpenAI-compatible and uses OpenAI image model/parameter controls.
- [ ] Local Studio request options include the selected image model/provider information.
- [ ] Google AI Studio image tool requests use the selected Gemini image model in backend image generation.
- [ ] A single generated image is stored/rendered once, not duplicated from partial/final events.
- [ ] Streaming Local Studio UI shows tool progress/details during image generation.
- [ ] Thinking/tool detail fields present in responses are retained and can be displayed by the UI.
- [ ] Automated unit tests cover Gemini and custom OpenAI payload/model behavior.
- [ ] Static frontend tests/checks cover the provider-aware UI behavior.
- [ ] Real system testing covers Gemini and custom OpenAI from API to Web, including simulated and real credential flows.
- [ ] Existing Playground remains available as a standalone Google AI Studio chat/search workflow.
- [ ] Existing Image Generation remains available as a standalone Google AI Studio chat/image workflow.
- [ ] Existing Account Management remains available as a standalone Google AI Studio account workflow.
- [ ] Existing Request Logs remain available as shared request management for all modules, including Local Studio.
- [ ] Local Studio provider wrapping/reuse does not regress the standalone base module flows.
- [ ] With the default Gemini provider selected and search/image tools disabled, Local Studio sends chat-only requests and produces normal chat responses.
- [ ] With default Gemini search/image tools enabled, Local Studio does not force tool invocation for ordinary chat prompts.
- [ ] With default Gemini search/image tools enabled, prompts that require search or image generation can trigger the matching enabled tool.
- [ ] With a custom OpenAI-compatible provider, enabled search/image tools are sent as optional tool definitions and tool invocation remains model/provider-directed.

## Required Verification

- Run targeted unit tests for Local Studio provider/model/image payload behavior.
- Run static frontend checks, including `node --check src/aistudio_api/static/app.js`.
- Run relevant pytest suites after implementation.
- Run WSL real environment tests using the real credentials documented in `AGENTS.md`.
- Real tests must include API-level and browser/UI-level validation for both Google AI Studio/Gemini and a custom OpenAI-compatible provider.
- Do not treat mocked tests as a substitute for real credential tests.

## Out of Scope

- Replacing the entire Local Studio UI.
- Removing, hiding, or merging the original standalone Playground, Image Generation, Request Logs, or Account Management pages.
- Adding unrelated image editing workflows outside the Local Studio Responses image tool.
- Changing non-Local-Studio image generation pages unless required by shared capability metadata.
- Pushing or merging without completing the requested verification workflow.

## Technical Notes

- Primary frontend files: `src/aistudio_api/static/app.js`, `src/aistudio_api/static/index.html`.
- Primary backend files: `src/aistudio_api/infrastructure/local_studio.py`, `src/aistudio_api/application/api_service.py`, `src/aistudio_api/domain/model_capabilities.py`.
- Primary tests: `tests/unit/test_local_studio.py`, existing static frontend tests.
- Repo memory notes require `node --check src/aistudio_api/static/app.js` after editing static Alpine code.
- User workflow requires starting from clean worktree, feature branch from master, full testing, commit, PR, master update, and branch cleanup.

## Research References

- `research/current-implementation.md` — current code paths and known log symptoms.
- `research/provider-image-capabilities.md` — provider/model capability design assumptions for Gemini and OpenAI-compatible image tools.
