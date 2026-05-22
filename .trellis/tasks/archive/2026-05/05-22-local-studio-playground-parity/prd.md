# Fix Local Studio Playground Parity

## Goal

Restore the original playground behavior after the OpenAI Local Studio addition, and upgrade Local Studio so it has the same practical interface coverage and diagnostics expected from the playground without regressing existing API or Web UI flows.

## What I Already Know

- The repository is on branch `fix/local-studio-playground-parity`, based on `master`.
- User reported the newly added Local Studio made the original playground unusable, with exported request logs at `C:\\Users\\bamboo\\Downloads\\aistudio-requests-1(2).json`.
- User requires the original full logic to keep working and not be broken by the fix.
- User reported Local Studio issues:
  - timeout does not take effect;
  - interface support is incomplete;
  - it must support OpenAI-compatible chat, OpenAI Responses, Gemini, Claude, free interface selection, model capabilities, token statistics, and streaming like the playground;
  - after clicking send, input text remains in the input box;
  - request records must be integrated for easier debugging.
- Real Local Studio key is stored at `C:\\Users\\bamboo\\Desktop\\GPT_image\\key.txt`; it must be used only at runtime and must not be committed or copied into artifacts.
- Existing playground frontend already supports interface modes `openai`, `responses`, `gemini`, and `claude` plus capability display, token usage, and stream parsing.
- Existing Local Studio frontend currently uses a separate `#studio` page and `/api/local-studio/*` backend that is primarily OpenAI Responses oriented.
- Existing request-log middleware logs `/v1*` and `/v1beta*` but not `/api/local-studio/*`.
- Request log sample confirms a playground `/v1/responses` chain is captured, including upstream browser 403 responses.

## Research References

- `research/request-log-analysis.md` — exported request log shape and logging coverage implications.

## Requirements

- Preserve and regression-test the original playground flows for OpenAI-compatible chat, OpenAI Responses, Gemini, Claude, model selection, model capabilities, token usage, streaming, and request logging.
- Extend Local Studio to support the same interface modes as the playground: OpenAI-compatible chat completions, OpenAI Responses, Gemini, and Claude.
- Let Local Studio users freely choose the interface mode independently of the global playground mode.
- Local Studio model loading and model picker must work for the selected interface mode.
- Local Studio chat sending must support non-stream and stream responses for supported interface modes.
- Local Studio must display assistant content, reasoning/thinking where available, token usage, and errors consistently with the playground.
- Local Studio timeout setting must affect upstream model-list and chat calls, including streaming calls.
- Local Studio should clear the draft input immediately after a send is accepted, while preserving the sent content in the conversation even if the upstream request fails.
- Local Studio chat/model upstream calls must be visible in request records using the same request-log UI and grouping semantics.
- Server-side Local Studio persistence must not store API keys/tokens.
- Existing Local Studio conversation CRUD, attachments, image tool fallback, and asset serving behavior must continue to work unless superseded by interface-mode parity.

## Acceptance Criteria

- [x] Unit tests cover Local Studio interface-mode payload routing/parsing for OpenAI chat, Responses, Gemini, and Claude.
- [x] Unit tests cover timeout propagation to upstream Local Studio model and chat clients.
- [x] Unit/static tests cover Local Studio draft clearing on send and Local Studio request-log eligibility.
- [x] Existing playground static tests continue passing.
- [x] Existing Local Studio tests continue passing or are updated for the new compatible behavior.
- [x] `node --check src/aistudio_api/static/app.js` passes after frontend edits.
- [x] Relevant pytest unit tests pass.
- [x] WSL real API test passes using runtime-only credentials from `C:\\Users\\bamboo\\Desktop\\GPT_image\\key.txt` and real account data under WSL.
- [x] Browser UI real smoke passes for original playground and Local Studio.
- [x] Request log UI shows Local Studio requests after request logging is enabled.

## Definition Of Done

- Tests added or updated for behavior changed in this task.
- Lint/syntax checks for edited frontend JavaScript pass.
- Existing old playground behavior is verified before final signoff.
- Real API and Web UI end-to-end checks pass in WSL as required by project instructions.
- Task metadata under `.trellis/tasks/05-22-local-studio-playground-parity/` is committed with the code changes.
- No secrets from the Local Studio key file are committed.

## Out Of Scope

- Changing account credentials, real account contents, or committed secret handling.
- Replacing the entire UI design.
- Adding new provider families beyond the existing playground modes.
- Fixing upstream account/auth 403 causes unrelated to this regression, unless directly caused by Local Studio changes.

## Technical Notes

- Likely files: `src/aistudio_api/static/app.js`, `src/aistudio_api/static/index.html`, `src/aistudio_api/static/style.css`, `src/aistudio_api/api/routes_local_studio.py`, `src/aistudio_api/api/app.py`, `src/aistudio_api/infrastructure/local_studio.py`, and Local Studio/static tests.
- Existing backend quality guideline includes a Local Studio contract that must be preserved and updated only if this task discovers a durable new rule.
- Request logging is implemented by `request_log_exchange_middleware` and `RequestLogStore` chain grouping.
