# Request Flow Research

## Relevant Current Paths

- `AIStudioClient.generate_content` captures an AI Studio request template, rewrites the body with `modify_body`, then calls `RequestReplayService.replay`.
- `AIStudioClient.generate_image` follows the same capture/rewrite/replay path with image-specific generation config.
- `AIStudioClient.stream_generate_content` captures the template and delegates the rewritten request to `StreamingGateway.stream_chat`, which sends via `BrowserSession.send_streaming_request`.
- Account rotation can use isolated `AIStudioClient` instances from `AccountClientPool`, so any request logging dependency must be passed to pooled clients too.
- Frontend is a single Alpine app under `src/aistudio_api/static/` with sidebar navigation and route hashes limited to `chat`, `images`, and `accounts` today.

## Implementation Implications

- The durable request record should be created at the final outbound boundary, after `modify_body`, so the saved body is exactly what is sent to AI Studio rather than the inbound OpenAI/Gemini-compatible request.
- A shared request log store should own both the persisted toggle and the entries; otherwise the main client and account-scoped clients can drift.
- Details should include raw body and parsed JSON body when possible. Rendering parsed JSON improves readability, while preserving raw body avoids information loss.
- Headers can contain sensitive authentication material, but the feature request explicitly asks for complete outbound requests. The UI should make no redaction that would lose information.

## Recommended MVP

- Add a file-backed `RequestLogStore` under `data/request-logs/`.
- Expose `/request-logs/status`, `/request-logs`, and `/request-logs/{id}` APIs.
- Record non-streaming text, image generation, and streaming AI Studio replay requests when enabled.
- Add a sidebar page for the toggle, list, structured detail, and raw detail.