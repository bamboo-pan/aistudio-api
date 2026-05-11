# 功能完整性改进

## Goal

把当前 AI Studio API 从“核心反代可用”推进到“功能闭环可用”：优先修复图像模型请求失败，补齐模型能力识别、账号凭证导入导出、前端/后端功能对齐和测试基线，让用户能可靠地使用文本、图像、账号池和管理界面。

## What I Already Know

* 用户明确需要功能完整性改进，并点名需要凭证导入/导出功能。
* 用户实际测试图像模型时遇到下游错误：`HTTP 400: MediaResolution is not supported`。
* 当前 `/v1/images/generations` schema 有 `n`、`size`，但应用服务实际只把 `prompt` 和 `model` 传给图像生成路径。
* 当前 Gemini 原生请求会把 `generationConfig.mediaResolution` 映射为内部 `media_resolution` 后继续下发，图像模型可能不支持该字段。
* 当前 OpenAI 模型列表硬编码，缺少模型能力注册表，后端无法根据模型能力校验字段，前端也无法隐藏无效控件。
* 当前前端会发送 `thinking`、`grounding`、`safety_off` 等字段，但 `ChatRequest` 未显式建模，部分 UI 设置可能被 Pydantic 忽略。
* 当前账号管理支持网页登录、列出、激活、改名、删除，但不支持导入、导出、备份恢复或凭证健康检查。
* 当前测试依赖基线不完整：现有虚拟环境缺少 `pytest`，pure HTTP 路径还存在未声明依赖/边界问题。

## Assumptions (Temporary)

* 本任务不应一次性完成所有长期产品化项，而应拆成可以落地的第一阶段 MVP。
* 第一阶段最有价值的是修复真实阻塞：图像模型 400、模型能力校验缺失、账号凭证迁移缺口、前端无效设置。
* 账号凭证导出涉及敏感信息，MVP 需要至少有明确风险提示和避免误导用户的接口/文案。

## Requirements (Evolving)

### MVP Scope

The user selected option 3 for the first implementation wave: image model repair, model capability registry, and credential import/export. Full frontend alignment is not part of this wave except for any minimal UI required to make credential import/export usable.

### P0 Requirements

* 修复图像模型生成请求中的不兼容 generation config，特别是不能向不支持的模型下发 `mediaResolution`。
* 引入模型能力注册表，用于描述模型支持文本、图像输入、图像输出、搜索、工具调用、thinking、流式输出和不支持字段。
* 让请求处理基于模型能力进行前置校验，并返回可理解的 400 错误，而不是透出难懂的底层 wire 错误。
* 补齐 `/v1/images/generations` 的核心参数处理，包括 `size`、`n`、返回格式和图像模型能力约束。
* For `/v1/images/generations`, support `n > 1` by performing sequential image-generation calls and aggregating the returned images.
* Image `size` should be handled through the model capability registry: supported sizes/aspect ratios are mapped and sent downstream when possible; unsupported values return a clear 400 error.
* 增加账号凭证导入和导出能力，至少支持现有账号 `auth.json` / Playwright storage state 的导入导出。
* Credential export MVP uses a project backup JSON package with a manifest and strong sensitive-data warnings.
* Credential import MVP accepts the project backup JSON package and compatible single-account Playwright storage state / `auth.json` content.
* Add backend APIs for credential import/export and a minimal WebUI entry point on the account management page.
* Do not add CLI import/export commands in this implementation wave.
* 补齐测试和依赖基线，确保新增行为可以通过单元测试或路由级测试验证。

### Later Scope Candidates

* 账号健康检查、账号层级标签、按模型自动选择账号。
* 独立生图页面、聊天图片上传、图像结果画廊和下载历史。
* OpenAI `/v1/responses`、`/v1/messages` 和 Gemini `countTokens` / embeddings / fileData。
* 结构化日志、ready health、管理端访问保护、Docker/WSL 部署体验。

## Acceptance Criteria (Evolving)

* [ ] 图像模型请求不再因继承或转发 `mediaResolution` 等不支持字段而失败。
* [ ] 模型能力注册表能被 `/v1/models`、请求校验和前端模型选择共同使用或稳定引用。
* [ ] 不支持的模型/参数组合在请求前返回清晰 400 错误。
* [ ] `/v1/images/generations` 对 `size`、`n`、响应格式和图像模型限制有明确行为。
* [ ] Requests with `n > 1` return multiple image results by sequential generation calls, with errors handled consistently if one call fails.
* [ ] Supported image `size` values are mapped according to model capability metadata; unsupported values produce a clear 400 response.
* [ ] 用户可以从账号管理接口导入凭证，并导出单账号或全部账号凭证。
* [ ] Exported credential backup package includes enough manifest metadata to restore account ids/names/emails when possible.
* [ ] Import rejects invalid JSON, malformed backup packages, and obviously incompatible storage-state content with clear errors.
* [ ] If credential import/export is exposed through the WebUI, the UI provides a minimal usable entry point with clear sensitive-data warnings.
* [ ] 测试依赖可用，相关单元/路由测试覆盖图像模型配置清理、模型能力校验和凭证导入导出。

## Definition of Done

* Tests added/updated for changed behavior.
* Existing unit tests pass in the configured Python environment.
* Docs or README updated when user-visible behavior changes.
* Sensitive credential import/export behavior has clear safety constraints.
* Changes follow existing FastAPI/service/infrastructure layering.

## Technical Approach

* Add a central model capability registry close to the API/application boundary and replace or wrap the existing hardcoded OpenAI model list with capability-aware metadata.
* Use capability metadata to sanitize generation config before rewriting AI Studio wire bodies, especially for image-output models that do not support `mediaResolution` or inherited text-generation fields.
* Extend image generation service behavior to support sequential `n` calls, size mapping/validation, and OpenAI-compatible response aggregation.
* Extend account storage/service/routes with import/export operations for project backup JSON packages and compatible single-account storage-state JSON.
* Add a minimal account-management WebUI affordance for importing/exporting credentials with clear sensitive-data warnings.
* Add focused tests for capability validation, image generation config cleanup, image `n` / `size` behavior, and credential import/export validation.

## Implementation Plan (Small PRs)

* PR1: Test/dependency baseline and model capability registry scaffold.
* PR2: Image model repair, config sanitization, `n` sequential generation, and `size` mapping/validation.
* PR3: Credential import/export backend APIs and account store/service support.
* PR4: Minimal WebUI import/export controls and README/user-facing docs.

## Out of Scope (Draft)

* Full `/v1/responses` or `/v1/messages` compatibility in the first implementation wave.
* Full account tier detection and automatic Pro/Ultra routing unless required for image model correctness.
* Full production auth system for the management UI in the first wave.
* Password-encrypted credential backup packages in the first wave.
* Full Docker/CI rollout unless needed to make the test baseline usable.
* Full frontend model/settings alignment beyond minimal credential import/export affordances.

## Technical Notes

* Likely affected API/service files: `src/aistudio_api/api/schemas.py`, `src/aistudio_api/api/routes_openai.py`, `src/aistudio_api/application/api_service.py`, `src/aistudio_api/application/chat_service.py`.
* Likely affected gateway files: `src/aistudio_api/infrastructure/gateway/wire_codec.py`, `src/aistudio_api/infrastructure/gateway/client.py`, `src/aistudio_api/infrastructure/gateway/streaming.py`.
* Likely affected account files: `src/aistudio_api/api/routes_accounts.py`, `src/aistudio_api/application/account_service.py`, `src/aistudio_api/infrastructure/account/account_store.py`.
* Likely affected frontend files: `src/aistudio_api/static/app.js`, `src/aistudio_api/static/index.html`, `src/aistudio_api/static/style.css`.
* Existing tests under `tests/unit/` cover parsers, request normalization, wire codec mapping, account auth activation, and gateway session readiness, but not route-level image generation, model capability validation, or credential import/export.

## Decisions

* First implementation wave includes image model repair, model capability registry, and credential import/export.
* Credential import/export should be exposed through backend APIs plus a minimal account-management WebUI entry point. CLI support is out of scope for the first wave.
* Credential export format is a project backup JSON package with a manifest and strong warning text, not password-encrypted in the MVP.
* `/v1/images/generations` should support `n > 1` through sequential generation calls.
* Image `size` should be mapped through model capability metadata where possible; unsupported size/model combinations should return 400.

## Open Questions

* None currently. Awaiting whole-PRD confirmation before implementation.