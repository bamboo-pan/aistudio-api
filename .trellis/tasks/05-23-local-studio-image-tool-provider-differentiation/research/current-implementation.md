# Current Implementation Notes

## Frontend

- `src/aistudio_api/static/app.js` initializes Local Studio image settings as provider-neutral fields: `localStudioImageToolEnabled`, `localStudioImageSize`, `localStudioImageQuality`, `localStudioImageBackground`, `localStudioImageFormat`, and `localStudioImageCompression`.
- `localStudioOptions()` always sends size/quality/background/output_format/output_compression when the Responses image tool is enabled.
- `localStudioPendingDetail` and `localStudioRunSummary` hard-code `gpt-image-2` in status text.
- `src/aistudio_api/static/index.html` renders a static `Image Tool` panel headed `gpt-image-2`, with OpenAI-style fields and OpenAI size note.
- `localStudioModelOptions` filters out `gpt-image-*` chat models but does not expose a separate image-model selection for Local Studio.
- Streaming Local Studio handling only consumes `local_studio.delta`, `local_studio.completed`, and errors; it appends `event.content`, `event.thinking`, and usage, but no structured tool-progress event.

## Backend

- `src/aistudio_api/infrastructure/local_studio.py` builds Responses payloads for Local Studio and emits `tools` entries for `web_search_preview` and `image_generation`.
- Existing unit tests assert the image tool is `gpt-image-2` for a Google provider, which is the behavior this task changes.
- `src/aistudio_api/application/api_service.py` detects Responses `image_generation` tools, removes the image tool from the text payload, optionally runs `handle_chat` when search is enabled, then calls `handle_image_generation`.
- `_responses_image_request()` uses `DEFAULT_IMAGE_MODEL` instead of a selected tool/model value, and maps only a small subset of sizes through `_image_size_for_google_provider()`.
- `_build_responses_image_generation_streaming_response()` emits full image items in `response.output_item.added`, `response.output_item.done`, and `response.completed`, plus `response.image_generation_call.partial_image`, so large base64 payloads are duplicated.

## Log Symptoms From `aistudio-requests-2.json`

- User message: `做成图片`.
- Outer request: `/api/local-studio/chat`.
- Inner request: `/v1/responses`.
- Upstream browser calls: first `GenerateContent` with `gemini-3.5-flash`, then image `GenerateContent` with `gemini-3.1-flash-image-preview`.
- Generated image was one 1024x1024 JPEG, about 800KB binary.
- Final Local Studio assistant message had content `Generated image` and two image entries.
- Intermediate thinking/text/tool process was present upstream but not visible in final UI.
