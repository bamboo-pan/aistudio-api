# brainstorm: 重构 playground 页面

## Goal

重构现有 Playground 页面，让它从单一聊天窗口升级为更适合代理调试和日常模型试用的工作台。目标是提升首屏信息组织、模型能力可见性、参数调整效率、对话可操作性和移动端可用性，同时保持当前后端 API 合约不变。

## What I already know

* 用户认为当前 Playground 页面设计不友好，希望重构整个页面并提升用户体验。
* 用户允许增加实用功能，但没有指定必须新增哪些功能。
* 当前前端是 `src/aistudio_api/static/index.html` + `app.js` + `style.css` 的 Alpine 单页应用。
* Playground 对应 `view === 'chat'`，侧边栏入口文字为 `Playground`。
* 当前 Playground 已有模型选择、聊天消息、文件上传、思考内容折叠、错误展示、配置下拉等能力。
* 模型能力来自 `/v1/models`，前端会根据 `selectedCaps` 控制 thinking/search/stream/safety/temperature/top_p/max_tokens 和文件上传可用性。
* 现有静态前端测试通过字符串断言覆盖关键能力，重构不能移除这些标记和行为。
* 图片生成、账号管理和控制面板已经有较新的工作台式布局，Playground 可以沿用其更密集、操作导向的视觉语言。

## Assumptions (temporary)

* 本任务优先重构 Playground，不改动图片生成、账号管理、控制面板的业务逻辑。
* 不新增后端 API；新增功能优先在前端状态和本地浏览器能力内完成。
* 页面应适合开发者反复调试模型代理，而不是做营销式首页。
* 必须保留现有聊天发送、流式输出、文件上传和模型能力 gating 行为。

## Product Direction

* 用户选择“综合工作台”：对话体验、参数/能力、附件和请求状态并重，适合日常调试。
* 视觉方向采用安静、密集、操作导向的开发者工具风格；避免营销式首页、装饰性大卡片和过度氛围化视觉。

## Open Questions

* 等待用户对完整 PRD 进行确认、修订或 override。

## Requirements (evolving)

* 重构 Playground 首屏布局，让模型、能力状态、参数、输入和输出的层次更清晰。
* 保留并优化现有聊天能力：文本输入、Shift+Enter 换行、Enter 发送、附件上传、错误展示、思考内容折叠。
* 让当前模型的能力和限制更可见，例如文件输入、搜索、推理、流式、参数是否可用。
* 将常用参数从隐藏设置中适当外显或分组，降低调试时反复打开下拉的成本；保留现有设置下拉作为完整配置入口。
* 增加实用前端功能：提示词模板/示例、请求摘要、对话清空、复制消息、参数预设或附件状态增强，优先选择不需要后端改动的功能。
* 空状态不做 landing page，而是直接呈现可用的 Playground 工作区和可点选示例。
* 移动端布局不能出现文字/按钮互相遮挡，关键操作必须可触达。
* 不破坏现有静态能力测试中依赖的行为和标记。

## Acceptance Criteria (evolving)

* [ ] Playground 页面有新的工作台式布局，并在桌面与移动端都能正常使用。
* [ ] 当前模型、模型能力、请求参数和附件状态比原页面更容易理解和操作。
* [ ] 聊天发送、流式响应、非流式响应、错误展示、thinking 折叠、文件上传仍按原逻辑工作。
* [ ] 至少新增两个实用前端功能，且不需要后端 schema 变更。
* [ ] 相关静态前端测试更新或继续通过。
* [ ] 在 Windows 本地和 WSL 真实环境完成必要验证。

## Definition of Done (team quality bar)

* Tests added/updated where appropriate.
* Lint / typecheck / relevant tests green.
* Docs/notes updated if behavior changes.
* Rollout/rollback considered if risky.
* Trellis task record, commit, finish-work, and push follow `develop_workflow.txt`.

## Out of Scope (explicit)

* 不改造后端聊天协议或 `/v1/chat/completions` 行为。
* 不引入大型前端框架或构建链。
* 不重写图片生成、账号管理、控制面板页面。
* 不实现服务端持久化聊天历史，除非后续明确要求。
* 不新增工具调用编辑器、结构化输出 schema 编辑器等更重的 API 调试功能；可为后续保留布局扩展点。

## Expansion Sweep

### Future evolution

* Playground 未来可能扩展为完整 API 调试台，支持 payload 查看、工具调用配置、结构化输出 schema、历史请求重放。
* 本次布局应预留右侧/侧栏区域，便于以后增加高级调试模块。

### Related scenarios

* 与图片生成页、账号管理页保持操作密度、按钮形态、状态提示和自定义选择器的一致性。
* 与模型能力验证保持一致：不可用能力不应被误导性展示为可操作。

### Failure & edge cases

* 模型列表加载失败、无可用模型、当前模型不支持附件、请求失败、流式中断时都需要清晰反馈。
* 移动端需要优先保证输入区、发送按钮、附件预览和关键设置不互相遮挡。

## Technical Approach

* 在现有 Alpine 静态页面内重构 `chat` 视图，不引入构建链或大型依赖。
* 将 Playground 改成三块式工作台：上方/左侧为会话主区域，右侧或折叠面板为模型能力与参数，底部为稳定输入栏。
* 对空状态加入可点击示例提示词/模板，点击后填充输入框。
* 在前端派生请求摘要，展示当前模型、附件数量、stream/thinking/search/safety 和采样参数。
* 为消息增加复制按钮，并提供清空会话动作。
* 保留现有配置下拉和自定义选择器逻辑，避免影响其他页面。

## Decision (ADR-lite)

**Context**: Playground 既要可聊天，也要服务代理调试；单纯聊天页会隐藏关键参数，纯 API 控制台又会降低日常试用效率。

**Decision**: 采用“综合工作台”方向，在不改后端 API 的前提下重构现有 `chat` 视图，外显模型能力、请求摘要和常用操作。

**Consequences**: 页面信息密度会比传统聊天页更高，需要通过响应式布局和清晰分组控制复杂度；重型调试能力暂不进入 MVP。

## Technical Notes

* Main frontend files: `src/aistudio_api/static/index.html`, `src/aistudio_api/static/app.js`, `src/aistudio_api/static/style.css`.
* Relevant tests: `tests/unit/test_static_frontend_capabilities.py`.
* Existing test anchors include `selectModel(m.id)`, `controlAvailable('thinking')`, `controlAvailable('stream')`, `attachChatFiles($event)`, `chatCanSend`, `selectedCaps.file_input`, and related file upload strings.
* Project uses plain static assets served by FastAPI; no bundler is present.