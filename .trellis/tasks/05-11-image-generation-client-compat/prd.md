# 简化图像生成客户端兼容

## Goal

让用户和第三方客户端调用图像生成模型时只需要表达“我要生成图像”，由后端自动处理 stream、response_format、接口形态、返回结构等兼容细节，尽量兼容 Cherry Studio 和常见 OpenAI-compatible 客户端，避免用户遇到“这个字段不行、那个格式不支持”的体验。

## What I already know

* 用户期望图像生成模型调用体验简单：选图像模型后就生成图像，兼容细节由后端兜底。
* 当前 `/v1/chat/completions` 会在 `stream=true` 且模型不支持流式时返回 400。
* 当前 `/v1/images/generations` 的 `ImageRequest` 只包含 `prompt`、`model`、`n`、`size`、`response_format`。
* 当前服务端只接受 `response_format=b64_json`，显式拒绝 `response_format=url`。
* 当前测试 `test_image_generation_rejects_url_response_format` 固化了拒绝 `url` 的行为，需要随着兼容策略更新。
* `AIStudioClient.generate_image()` 已经可以从 AI Studio 返回中解析图片字节，服务端可以编码成 base64 返回。

## Research References

* [`research/image-client-compat.md`](research/image-client-compat.md) — Cherry Studio 常见情况下会省略 `response_format` 并可处理 base64；部分 OpenAI 兼容客户端可能请求或期待 `url`，当前仓库只匹配 `b64_json`。

## Requirements

* 后端识别图像输出模型时，应优先走图像生成语义，而不是要求用户理解 chat/image endpoint 的差异。
* 对图像模型请求，后端应自动关闭或忽略不适用的流式输出，而不是向用户暴露 `streaming responses` 错误。
* `/v1/images/generations` 应兼容常见客户端发送的 `response_format` 变体，至少不因 `url` 直接失败。
* 后端应返回客户端可消费的图像结果，默认保持 OpenAI-compatible 的 `data` 数组结构。
* 对无法兼容的参数，应尽量采用合理默认值或忽略无害字段；只有确实无法完成图像生成时才返回明确错误。
* 模型元数据应尽量帮助客户端识别图像生成能力，避免客户端误判模型只能聊天。

## Acceptance Criteria

* [ ] Cherry Studio 使用图像生成接口调用 `gemini-3.1-flash-image-preview` 能成功得到图片。
* [ ] 请求 `response_format=url` 不再因为格式本身直接 400；后端自动返回可兼容的图像结果。
* [ ] 用户通过 chat completions 选择图像模型并发送绘图提示时，不会因为 `stream=true` 报错。
* [ ] 原有 `b64_json` 图片生成行为继续可用。
* [ ] 不支持的尺寸仍有清晰错误，避免静默生成错误比例/尺寸。
* [ ] 单元测试覆盖 Cherry Studio/通用客户端的兼容请求形态。

## Definition of Done

* Tests added/updated for image request normalization and compatibility.
* Relevant unit tests pass.
* Docs or README usage notes updated if public behavior changes.
* Trellis check runs after implementation.

## Technical Approach

Chosen direction: full automatic backend compatibility around image-capable models.

* Normalize image generation requests before validation: default unsupported/omitted client fields to server-supported behavior.
* Treat `response_format=url` as a compatibility request rather than a hard failure. Since the backend currently has image bytes, it can return `b64_json` and optionally include a data URL/string if needed by clients.
* Detect image-output models in chat completions and route image-model prompts through image generation semantics when possible, including automatic stream downgrading.
* Keep strict validation only for cases that affect actual generation correctness, such as unsupported image size or non-image model.

## Decision (ADR-lite)

**Context**: The existing implementation is technically explicit but leaks backend limitations into user/client configuration. This causes common clients to fail unless users know the exact supported combination.

**Decision**: Implement full automatic compatibility. Image-capable model calls should be handled as image generation whether the client reaches the backend through chat-style or image-style OpenAI-compatible paths, with backend-side normalization for stream and response format differences.

**Consequences**: A compatibility layer increases backend responsibility but makes client setup much simpler and aligns with the project goal of being an OpenAI-compatible AI Studio gateway.

## Out of Scope

* Hosting generated images as persistent public URLs unless explicitly chosen.
* Supporting image editing/variation endpoints in this task.
* Changing AI Studio capture/replay internals unless required for request routing.

## Technical Notes

* Image route: `src/aistudio_api/api/routes_openai.py`
* Request schemas: `src/aistudio_api/api/schemas.py`
* Image service: `src/aistudio_api/application/api_service.py`
* Model capabilities: `src/aistudio_api/domain/model_capabilities.py`
* Image tests: `tests/unit/test_image_generation_service.py`

## Open Questions

* None before final PRD confirmation.