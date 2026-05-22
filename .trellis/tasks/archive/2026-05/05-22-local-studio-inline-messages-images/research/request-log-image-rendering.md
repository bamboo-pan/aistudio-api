# Request Log Image Rendering Findings

## Source

- User-provided export: `C:\Users\bamboo\Downloads\aistudio-requests-1(3).json`

## Findings

- The export contains one complete request group with four phases: `client_request`, `upstream_request`, `upstream_response`, and `client_response`.
- The large body is the upstream streamed Responses phase, about 6.18 MB. The final client response is small, about 2 KB.
- The client response shape is the important UI contract: it should contain `conversation.messages`, where assistant messages can carry an `images` array with `/api/local-studio/assets/...` URLs.
- The current non-stream backend saves image candidates from final parsed payloads. The stream backend only accumulates text/thinking/usage and does not persist image candidates observed in stream events or the completed response.
- The current frontend waits for the server conversation before showing the user message in Local Studio, unlike Playground which pushes the user message immediately.
- Local Studio Responses image generation should rely on the `image_generation` tool result only; `/images/generations` fallback is not part of this task's desired behavior.

## Implementation Targets

- Add optimistic Local Studio user message insertion in the static frontend for non-rerun sends.
- Ensure the temporary optimistic message is reconciled when the server returns the saved conversation, and restored draft/files are not lost on failures.
- Persist image candidates during Local Studio streaming so generated images appear in the saved conversation and UI.
- Add regressions that no-candidate or failed Responses image-tool requests do not call `/images/generations`.
- Harden frontend image URL extraction for Local Studio image objects that include `url`, `path`, `data_url`, `b64_json`, `b64`, or `result`.
