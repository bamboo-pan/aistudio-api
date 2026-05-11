# Research: OpenAI-Compatible Image Generation Client Compatibility

- **Query**: Research common OpenAI-compatible image generation client behavior relevant to this task, especially Cherry Studio and generic clients calling `/v1/images/generations`. Focus on request fields (`model`, `prompt`, `n`, `size`, `response_format`), whether clients commonly send `response_format=url` or omit it, expected response shapes for `url` vs `b64_json`, and model metadata hints for image generation. Map findings to this repo's constraints: it currently supports image bytes from AI Studio and can return `b64_json`; it currently rejects `response_format=url`.
- **Scope**: mixed
- **Date**: 2026-05-11

## Findings

### Files Found

| File Path | Description |
|---|---|
| `src/aistudio_api/api/schemas.py:44` | Local OpenAI-compatible `ImageRequest` schema: `prompt`, `model`, `n`, `size`, `response_format`, defaulting `response_format` to `b64_json`. |
| `src/aistudio_api/application/api_service.py:75` | Local image request validation: `n` range checks and rejection of any `response_format` other than `b64_json`. |
| `src/aistudio_api/application/api_service.py:299` | Local `/v1/images/generations` service handler: loops `n` times, calls AI Studio, base64-encodes returned image bytes, and returns `{created, data:[{b64_json, revised_prompt}]}`. |
| `src/aistudio_api/domain/model_capabilities.py:51` | Local model metadata exposes `image_generation.sizes` and `image_generation.response_formats`, currently only `['b64_json']`. |
| `tests/unit/test_image_generation_service.py:52` | Local tests verify multi-image aggregation returns base64 JSON entries. |
| `tests/unit/test_image_generation_service.py:81` | Local tests verify `response_format='url'` is currently rejected before any AI Studio call. |
| `tests/unit/test_model_capabilities.py:9` | Local tests verify image model metadata advertises `image_output` and only `b64_json`. |

### Code Patterns

Local repo request contract:

```py
class ImageRequest(BaseModel):
    prompt: str
    model: str = DEFAULT_IMAGE_MODEL
    n: int = 1
    size: str = "1024x1024"
    response_format: str = "b64_json"
```

Source: `src/aistudio_api/api/schemas.py:44`.

Local validation rejects URL output explicitly:

```py
if req.response_format != "b64_json":
    raise ValueError("response_format must be 'b64_json'; URL responses are not available")
```

Source: `src/aistudio_api/application/api_service.py:79`.

Local response construction is already OpenAI-style for base64 image data:

```py
b64 = base64.b64encode(img.data).decode("ascii")
data.append({"b64_json": b64, "revised_prompt": output.text or ""})
return {"created": int(time.time()), "data": data}
```

Source: `src/aistudio_api/application/api_service.py:339`.

Local model metadata adds non-standard but useful hints:

```py
data["image_generation"] = {
    "sizes": [size.to_public_dict() for size in self.image_sizes.values()],
    "response_formats": ["b64_json"],
}
```

Source: `src/aistudio_api/domain/model_capabilities.py:51`.

Cherry Studio direct `/v1/images/generations` patterns:

- `src/renderer/src/pages/paintings/NewApiPage.tsx:313` builds an OpenAI-style image generation JSON body with `prompt`, `model`, optional `size`, `n`, `quality`, and `moderation`; it does not include `response_format` in that path.
- `src/renderer/src/pages/paintings/DmxapiPage.tsx:365` builds a V1 generation request for `${dmxapiProvider.apiHost}/v1/images/generations` with `prompt`, `model`, `n`, optional `size`, optional `seed`, style prompt changes, and optional base64 input image; no direct `response_format` unless a user/provider `extend_params` entry supplies one.
- `src/renderer/src/pages/paintings/OvmsPage.tsx:184` builds an image generation body with `model`, `prompt`, `size`, `num_inference_steps`, and `rng_seed`; its type includes `response_format?: 'url' | 'b64_json'`, but the request body shown omits it.
- `src/renderer/src/pages/paintings/AihubmixPage.tsx:373` routes several provider-specific models to `/v1/images/generations` with OpenAI-compatible URL/header shape; nearby request bodies include `prompt` and `model` plus provider-specific fields, not a mandatory `response_format`.

Cherry Studio AI SDK path:

- `src/renderer/src/aiCore/AiProvider.ts:388` maps Cherry's `GenerateImageParams` into AI SDK `generateImage` args: `prompt`, `size`, `n`, and optional abort signal. It does not pass `response_format`.
- `src/renderer/src/aiCore/AiProvider.ts:443` converts AI SDK image results by reading `result.images[].base64` and producing `data:<mime>;base64,...` strings.
- `packages/aiCore/src/core/runtime/__tests__/generateImage.test.ts:63` and `:95` show Cherry's runtime expects AI SDK image generation results to include base64-capable image objects, and tests minimal calls with only `model` and `prompt`, plus optional `n` and `size`.
- `.changeset/openai-compatible-image-response-format.md:7` records a Cherry Studio compatibility fix: `OpenAICompatibleImageModel.doGenerate` had unconditionally added `response_format: "b64_json"`; newer GPT Image models could reject that, so Cherry patched the compatible route to use a `hasDefaultResponseFormat` guard. This is strong evidence that current Cherry-compatible flows may omit `response_format`, and that hard-requiring or hard-injecting it can break some OpenAI-compatible providers.

Generic OpenAI SDK/client patterns:

- OpenAI Python and Node SDKs expose `/images/generations` as `client.images.generate(...)` and accept `prompt` plus optional `model`, `n`, `size`, `quality`, `style`, and `response_format`.
- In OpenAI Python, omitted optional params are represented as `Omit`, so callers who do not pass `response_format` do not send it. The generated request body includes a `response_format` key only when the caller supplied a non-omitted value.
- OpenAI Node's image generation method posts the caller-provided body directly to `/images/generations`; its examples include a minimal request with only `prompt`.
- Current OpenAI SDK docs preserve legacy `response_format?: 'url' | 'b64_json'`, but document it as DALL-E-era behavior: `url` is available for DALL-E 2/3, while GPT Image models always return base64 and do not support that parameter.
- The AI SDK `generateImage()` abstraction accepts `model`, `prompt`, optional `n`, optional `size`, optional `aspectRatio`, and provider options; it returns generated files with `base64`, `uint8Array`, and `mediaType`. Its OpenAI-compatible provider exposes `.imageModel('model-id')` and basic image generation with `prompt` plus `size`, not `response_format`.

Expected OpenAI-compatible response shapes:

- URL response shape is the legacy OpenAI image object shape: `{ "created": <unix>, "data": [{ "url": "https://..." }] }`, optionally with `revised_prompt` for supported models. OpenAI URLs are time-limited.
- Base64 response shape is `{ "created": <unix>, "data": [{ "b64_json": "..." }] }`, optionally with `revised_prompt`; modern GPT Image responses may also expose top-level metadata like `background`, `output_format`, `quality`, `size`, and `usage`.
- SDK-level image object types make `b64_json`, `url`, and `revised_prompt` optional because the selected response format/model determines which key is present.
- The Responses API image-generation tool is separate from `/v1/images/generations`; its image-generation call output uses base64 in `result`. This matters for model metadata and client expectations, but not for this repo's `/v1/images/generations` handler.

Model metadata hints for image generation:

- The standard OpenAI `/v1/models` shape is minimal (`id`, `object`, `created`, `owned_by`) and does not reliably advertise image-generation response formats.
- Cherry Studio uses several client-side hints rather than relying only on `/v1/models`: provider extension flags like `supportsImageGeneration`, endpoint type values including `image-generation`, and regex/model-name detection for models such as `gpt-image-*`, `gemini-*-image-*`, and other dedicated image models.
- Cherry model types also support optional `capabilities`, `endpoint_type`, and `supported_endpoint_types`, but the searched `/v1/images/generations` paths primarily route from configured provider/page/model logic.
- This repo's extra `capabilities` and `image_generation` metadata are non-standard but useful for clients that inspect model details. Currently advertising only `response_formats: ['b64_json']` matches the actual handler behavior.

Compatibility mapping for this repo:

- Clients omitting `response_format`: this repo accepts them because `ImageRequest.response_format` defaults to `b64_json`; the response shape is OpenAI-style base64. This aligns with modern OpenAI GPT Image behavior and Cherry Studio's AI SDK/direct request paths that commonly omit `response_format`.
- Clients sending `response_format='b64_json'`: this repo accepts them and returns `{created, data:[{b64_json, revised_prompt}]}`. This aligns with AI Studio's current byte-output constraint.
- Clients sending `response_format='url'`: this repo currently rejects them with a 400 before calling AI Studio. That is incompatible with legacy DALL-E-style generic clients that explicitly request URL output, and with callers that assume omitted legacy DALL-E `response_format` defaults to URL. It is not clearly required by current Cherry Studio paths found in this research.
- Because this repo currently has only image bytes from AI Studio, a true OpenAI-style `url` response would need a retrievable URL backed by stored/served image bytes. Without that, `b64_json` is the only response format that faithfully maps to current capabilities.
- Model metadata currently tells inspecting clients that only `b64_json` is supported. If behavior changes to support URL output, the metadata should remain synchronized with the real response formats.

### External References

- [OpenAI image generation guide](https://developers.openai.com/api/docs/guides/image-generation) — Current guide says the Image API returns base64-encoded image data for GPT Image models, supports `n` for multiple images, and describes size/quality/output-format customization.
- [OpenAI Python `ImageGenerateParams`](https://github.com/openai/openai-python/tree/main/src/openai/types/image_generate_params.py#L13-L111) — Defines required `prompt`, optional `model`, `n`, `response_format`, and `size`; documents `response_format` as `url`/`b64_json` for DALL-E 2/3 and unsupported for GPT image models, which always return base64.
- [OpenAI Python `Image`](https://github.com/openai/openai-python/tree/main/src/openai/types/image.py#L0-L28) — Response image object has optional `b64_json`, optional `url`, and optional `revised_prompt`.
- [OpenAI Node image response/types](https://github.com/openai/openai-node/tree/main/src/resources/images.ts#L96-L119) — Same optional `b64_json`, `url`, and `revised_prompt` fields; `url` is documented as unsupported for GPT image models.
- [OpenAI Node image request/types](https://github.com/openai/openai-node/tree/main/src/resources/images.ts#L718-L840) — Defines `prompt`, optional `model`, optional `n`, optional `response_format`, and optional `size` for `/images/generations`.
- [AI SDK `generateImage()` reference](https://ai-sdk.dev/docs/reference/ai-sdk-core/generate-image) — Accepts `model`, `prompt`, optional `n`, optional `size`, and returns files with `base64`, `uint8Array`, and `mediaType`.
- [AI SDK OpenAI-compatible provider](https://ai-sdk.dev/providers/ai-sdk-providers/openai-compatible) — Exposes `.imageModel()` and basic image generation via OpenAI-compatible providers with `prompt` and `size`.
- [Cherry Studio `NewApiPage.tsx`](https://github.com/cherryhq/cherry-studio/tree/main/src/renderer/src/pages/paintings/NewApiPage.tsx#L297-L340) — Direct `/v1/images/generations` request body includes `prompt`, `model`, optional `size`, `n`, `quality`, and `moderation`, without `response_format` in the found path.
- [Cherry Studio `AiProvider.ts`](https://github.com/cherryhq/cherry-studio/tree/main/src/renderer/src/aiCore/AiProvider.ts#L388-L414) — AI SDK generation path passes `prompt`, `size`, and `n`, then converts generated image base64 to data URLs.
- [Cherry Studio changeset on OpenAI-compatible image response format](https://github.com/cherryhq/cherry-studio/tree/main/.changeset/openai-compatible-image-response-format.md#L7-L8) — Notes that unconditional `response_format: "b64_json"` caused 400s on newer GPT image models, so the compatible route was patched to avoid always adding it.
- [Cherry Studio model detection](https://github.com/cherryhq/cherry-studio/tree/main/src/renderer/src/config/models/vision.ts#L132-L245) — Image generation model support is inferred through regexes, provider type, and dedicated image model detection.

### Related Specs

- Not checked; this was a bounded research pass for the supplied task output path. Relevant local contracts are listed above from source and tests.

## Caveats / Not Found

- `python ./.trellis/scripts/task.py current --source` reported no active task; the user supplied the exact destination task path, so this file was written there.
- Direct fetch of the old `platform.openai.com/docs/api-reference/images/create` URL returned 404/redirect behavior; current guide plus generated official Python/Node SDK types were used for exact request/response contracts.
- Cherry Studio evidence comes from repository search snippets, not a full local checkout. The searched paths did not show Cherry commonly sending `response_format='url'` for `/v1/images/generations`.
- Generic legacy OpenAI clients may still explicitly request `response_format='url'`, or may omit it while expecting DALL-E-era URL defaults. That behavior is real in OpenAI SDK types/docs, but was not found as a Cherry Studio default for the relevant paths.