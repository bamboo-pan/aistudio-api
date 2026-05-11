# 修复图像参数下拉与参数支持

## Goal

修复图片生成页尺寸下拉框无法查看全部选项、无法用滚轮或键盘继续选择的问题，并补齐前端与模型能力元数据中对当前已实现图像生成参数的呈现，让用户能清楚知道哪些参数可用、哪些参数暂不支持。

## What I Already Know

* 用户截图显示尺寸下拉被截断，只露出部分选项。
* 前端使用自绘 `.cselect`，尺寸下拉只有点击选择，没有键盘方向键/Enter/Escape 交互。
* `.cselect-menu` 本身有 `overflow-y:auto`，但图片表单面板 `.image-panel` 使用 `overflow:hidden`，下拉菜单会被父容器裁剪。
* 图像尺寸来自 `/v1/models` 返回的 `image_generation.sizes`。
* 后端当前 `ImageRequest` 支持 `prompt`、`model`、`n`、`size`、`response_format`。
* 模型能力元数据当前公开 `image_generation.sizes` 和 `image_generation.response_formats`，没有公开 `n` 范围、默认值或其它图像参数支持状态。
* 2026-05-11 WSL 真实账号探测确认 `gemini-3-pro-image-preview` 接受 `output_image_size` 的 `2K` 和 `4K`，分别返回 `2816x1536` 与 `4096x4096` 图片；当前代码把 pro image 和 flash image 共用 `DEFAULT_IMAGE_SIZES`，低估了 pro image 能力。

## Requirements

* 图片生成页的模型和尺寸下拉菜单必须能展示完整选项，菜单内容可滚动，不被父级面板截断。
* 尺寸列表必须包含当前后端/模型能力中所有实际支持的分辨率，不能只显示部分默认尺寸。
* `gemini-3-pro-image-preview` 的尺寸能力必须与 `gemini-3.1-flash-image-preview` 拆开，pro image 需要公开并接受已实测可用的 2K/4K 分辨率。
* 自绘下拉必须支持基础键盘操作：聚焦后打开，方向键移动，高亮当前候选项，Enter/Space 选择，Escape 关闭。
* 鼠标滚轮应能在打开的下拉菜单内部滚动选项。
* 前端图片生成表单应基于模型能力元数据展示已实现的图像参数：尺寸、数量范围、响应格式。
* 后端 `/v1/models` 的 `image_generation` 元数据应公开已实现图像参数的默认值、范围/枚举和暂不支持字段，避免用户误以为参数支持不完整但无处确认。
* `/v1/images/generations` 对未实现的 OpenAI 图片参数应保持兼容接收或给出清晰错误，不应静默承诺真正没有实现的效果。
* 保持现有图片生成行为：默认 `1024x1024`、`n=1`、前端请求 `response_format:'url'`，后端仍能返回 URL/data URL 兼容结果。

## Acceptance Criteria

* [ ] 在图片生成页打开尺寸下拉时，所有尺寸选项都可通过滚轮看到。
* [ ] 图片生成页尺寸下拉列出当前后端声明支持的全部分辨率。
* [ ] 选择 `gemini-3-pro-image-preview` 时，尺寸下拉和 `/v1/models` 元数据包含 pro image 的 2K/4K 分辨率。
* [ ] `/v1/images/generations` 对 `gemini-3-pro-image-preview` 的 2K/4K 请求映射到 AI Studio `output_image_size` 的 `2K`/`4K`。
* [ ] 在图片生成页打开尺寸下拉后，方向键、Enter/Space、Escape 可以完成移动、选择和关闭。
* [ ] 模型下拉和其它现有自绘下拉不会因键盘支持而回归。
* [ ] `/v1/models` 中图像模型的 `image_generation` 元数据包含尺寸、响应格式、数量范围/默认值和不支持字段信息。
* [ ] 后端图像参数验证有测试覆盖，未支持参数不会被静默当作已生效参数。
* [ ] 前端静态能力测试覆盖下拉键盘入口和图像参数元数据消费。
* [ ] 相关单元测试通过。

## Definition Of Done

* 测试新增或更新，覆盖前端静态行为和后端能力元数据/参数验证。
* `pytest` 相关测试通过。
* UI 变更保持现有简洁控制台风格，不引入新的页面结构。
* 文档或模型能力元数据足以说明实际支持边界。

## Technical Approach

* 修复 CSS 裁剪：允许图片面板/表单面板中的自绘下拉菜单溢出显示，必要时提高菜单层级并限制菜单自身最大高度。
* 给自绘选择器增加通用键盘状态与处理函数，复用于模型、尺寸、设置项等现有 `.cselect`。
* 扩展 `image_generation` 元数据，用结构化字段描述 `n`、`response_format`、`size` 以及 unsupported/ignored 字段。
* 拆分 image model 的尺寸能力：flash image 保持已验证 512/1K 档，pro image 增加已验证 `2K`/`4K` 输出尺寸映射。
* 扩展 `ImageRequest` 仅声明 OpenAI 兼容字段；真正未实现的字段由服务层明确拒绝或标记为忽略，避免虚假支持。

## Research References

* [`research/pro-image-resolution-probe.md`](research/pro-image-resolution-probe.md) — WSL 真实账号探测确认 `gemini-3-pro-image-preview` 支持 `2K`/`4K` 输出尺寸 token。

## Decision (ADR-lite)

**Context**: 用户同时遇到前端选择器交互问题，并质疑图像参数支持是否完整。当前实现既有 UI 裁剪，也缺少能力元数据说明。

**Decision**: 优先修复当前 UI 交互，同时把已实现参数能力公开清楚；不在本任务里实现 AI Studio 底层无法可靠映射的生成效果参数。

**Consequences**: 前端体验会立刻改善，客户端能读取更完整的能力元数据；部分 OpenAI 图片参数仍可能明确报不支持，需要未来基于 AI Studio 捕获能力再映射。

## Out Of Scope

* 不新增真实的 AI Studio 底层图像质量、风格、背景透明、压缩等效果映射，除非现有网关已经能可靠支持。
* 不重做整个前端设计系统。
* 不改账号轮询、聊天或 Gemini 路由行为。

## Technical Notes

* 前端入口：`src/aistudio_api/static/app.js`、`src/aistudio_api/static/index.html`、`src/aistudio_api/static/style.css`。
* 能力元数据：`src/aistudio_api/domain/model_capabilities.py`。
* 请求模型和验证：`src/aistudio_api/api/schemas.py`、`src/aistudio_api/application/api_service.py`。
* 现有测试：`tests/unit/test_static_frontend_capabilities.py`、`tests/unit/test_model_capabilities.py`、`tests/unit/test_image_generation_service.py`。
* 高分辨率实测记录：`.trellis/tasks/05-11-image-params-dropdown-fix/research/pro-image-resolution-probe.md`。