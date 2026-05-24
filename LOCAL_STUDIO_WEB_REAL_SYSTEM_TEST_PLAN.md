# Local Studio WebUI 真实系统测试计划

## 目标

这份计划用于验证 Local Studio 以及它复用的 WebUI 基础模块在真实环境中的完整用户路径。测试必须从用户真实入口出发，覆盖浏览器 UI、后端 API、上游 provider、请求记录和本地持久化，不用 mock 结果替代真实链路。

重点回归两个已报告问题：

* Google AI Studio provider 在 Local Studio Responses 模式下开启图片工具后，对话触发生图时上游返回 `Please enable tool_config.include_server_side_tool_invocations to use Built-in tools with Function calling.`。
* 自定义 OpenAI-compatible provider 在 Local Studio Responses 模式下开启 search 后，上游流式 HTTP 400 被后端错误读取为 `httpx.ResponseNotRead`，导致 ASGI 异常。

## 测试原则

* 所有 P0/P1 用例都在 WSL 临时目录的新副本中运行，不能直接污染开发工作区。
* 每个真实用户路径必须同时有 API 级验证和浏览器 UI 级验证。
* 请求记录必须开启，关键用例要检查完整生命周期：`client_request`、`upstream_request`、`upstream_response`、`client_response`。
* Provider、Interface、Stream、Search、Image Tool、Cache、Reasoning、附件和会话操作按下面的组合矩阵覆盖。
* 工具开关表示“允许使用”，不是“强制调用”。普通聊天在工具开启时仍必须能正常回答。
* 测试可引用密钥/凭据路径，但不能把真实 token、cookie、storage state、请求日志导出或生成图片提交到 Git。

## 真实环境

| 项目 | 要求 |
| --- | --- |
| WSL 工作目录 | 在 `/home/bamboo` 下新建临时目录，例如 `/home/bamboo/aistudio-api-system-test-YYYYMMDD-HHMMSS` |
| Google AI Studio 凭据 | 使用 `AGENTS.md` 指定的真实账号目录：Windows `\\wsl.localhost\Ubuntu-24.04\home\bamboo\aistudio-api\data\accounts`，WSL `/home/bamboo/aistudio-api/data/accounts` |
| OpenAI-compatible key | Windows `C:\Users\bamboo\Documents\github\key.txt`，WSL `/mnt/c/Users/bamboo/Documents/github/key.txt` |
| 浏览器 | Playwright/Camoufox 可启动真实 WebUI；UI 测试需截图和 console/network 记录 |
| 服务端口 | 优先使用临时端口，例如 `18080`，避免和本机开发服务冲突 |
| 数据目录 | 为每次测试设置独立 `AISTUDIO_LOCAL_STUDIO_DIR`、`AISTUDIO_REQUEST_LOGS_DIR`、`AISTUDIO_GENERATED_IMAGES_DIR`、`AISTUDIO_IMAGE_SESSIONS_DIR` |

推荐启动前置：

```bash
set -euo pipefail
set +x
RUN_ROOT="/home/bamboo/aistudio-api-system-test-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RUN_ROOT"
rsync -a --delete --exclude .git --exclude .venv --exclude venv /mnt/c/Users/bamboo/Desktop/aistudio-api_u1/ "$RUN_ROOT/repo/"
cd "$RUN_ROOT/repo"
python3 -m venv venv
. venv/bin/activate
pip install -e .
playwright install firefox
export AISTUDIO_PORT=18080
export AISTUDIO_ACCOUNTS_DIR=/home/bamboo/aistudio-api/data/accounts
export AISTUDIO_LOCAL_STUDIO_DIR="$RUN_ROOT/data/local-studio"
export AISTUDIO_REQUEST_LOGS_DIR="$RUN_ROOT/data/request-logs"
export AISTUDIO_GENERATED_IMAGES_DIR="$RUN_ROOT/data/generated-images"
export AISTUDIO_IMAGE_SESSIONS_DIR="$RUN_ROOT/data/image-sessions"
export OPENAI_COMPAT_KEY_FILE=/mnt/c/Users/bamboo/Documents/github/key.txt
python main.py
```

读取 OpenAI key 时只在测试进程内读取，禁止打印：

```bash
OPENAI_COMPAT_API_KEY="$(tr -d '\r\n' < "$OPENAI_COMPAT_KEY_FILE")"
```

## 覆盖维度

| 维度 | 必测取值 | 说明 |
| --- | --- | --- |
| WebUI 入口 | `#chat`、`#studio`、`#images`、`#requests`、`#accounts` | Local Studio 不能破坏基础业务线 |
| Provider | Google AI Studio、OpenAI-compatible | Google 走内置账号；OpenAI-compatible 走 Base URL + Token |
| Local Studio Interface | OpenAI Chat、OpenAI Responses、Gemini、Claude | UI 允许切换的模式都要测；不兼容组合必须优雅失败 |
| Stream | on、off | SSE 和普通 JSON 响应都要覆盖 |
| Search | off、on | on 时必须作为可选能力，不得强制普通问题走工具 |
| Image Tool | off、on | 仅 Responses 面板有效；Google 和 OpenAI-compatible 控件/参数不同 |
| Reasoning | off、high + summary auto | 仅在能力可用时发送；不可用时 UI 控件禁用或请求省略 |
| Cache | 首次 miss、重复 hit、不同 namespace miss | Local request cache 必须按 provider/mode/model/body/token hash 隔离 |
| 附件 | 无附件、图片、文本/PDF 类文件 | 只在当前模型能力允许时发送；不支持时 UI 必须阻止或提示 |
| 会话 | 新建、发送、刷新恢复、重跑、重命名、单删、批量删除 | 验证本地持久化和 UI 状态恢复 |
| 请求记录 | 关闭、开启、查看详情、导出、删除 | 开启后必须保存完整 lifecycle，敏感字段必须脱敏 |

## 组合规则

下面规则用于把“所有真实用户路径组合”落成可执行矩阵，避免只测单点成功路径。

1. 对每个有效的 `Provider x Interface` 组合，必须运行基础聊天 `Stream on/off x Search off/on` 四种组合。
2. 对每个 Responses 组合，必须额外运行 `Image Tool off/on x Search off/on` 四种组合，并验证普通问题不会因为工具开启而强制调用工具。
3. 对每个 Provider 至少运行一次 cache miss/hit/namespace miss 三连测试。
4. 对每个 Provider 至少运行一次图片附件和一次非图片附件路径；如果模型不支持附件，预期结果是 UI 阻止发送并给出错误提示。
5. 对每个 Provider 至少运行一次会话恢复和重跑；其中一次必须在页面刷新后恢复。
6. 每个预期失败或 provider 不兼容组合必须验证“优雅失败”：前端显示可理解错误、会话保存错误、请求记录完整、服务健康接口仍可用。
7. 每个 P0 bug 回归用例必须同时保留 API 原始响应、WebUI 断言、请求记录 group id、服务端 stderr 摘要和截图。

## P0 启动与共享服务

| ID | 路径 | 步骤 | 通过标准 |
| --- | --- | --- | --- |
| BOOT-01 | API | 启动服务后请求 `/api/local-studio/health`、`/request-logs/status`、`/v1/models`、`/v1beta/models` | 全部返回 200；模型列表非空；无未捕获异常 |
| BOOT-02 | UI | 打开 `/static/index.html#studio`，再依次进入 `#chat`、`#images`、`#requests`、`#accounts` | 页面可导航，核心控件可见，console 无错误 |
| LOG-01 | API + UI | 在 `#requests` 开启请求保存，然后 API 查询 `/request-logs/status` | UI 显示保存开启，API `enabled=true` |
| LOG-02 | API + UI | 执行一次 Local Studio 请求后打开请求详情、导出当前、删除当前 | 阶段卡片完整；导出 JSON 可解析；删除后列表消失 |
| SEC-01 | API + UI | 使用 OpenAI-compatible token 加载模型后检查 request log 导出 | `api_key`、`apiKey`、`token`、`Authorization` 都不出现真实 key；只允许 `***` 或 `Bearer ***` |

## P0 Local Studio - Google AI Studio Provider

| ID | Interface | Stream | Search | Image Tool | Cache | 用户路径 | 通过标准 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| G-LS-01 | Responses | on | off | off | miss | 选择 Google AI Studio，加载模型，选聊天模型，发送 `回复 ok` | UI 流式显示 assistant；请求记录含 `/api/local-studio/chat` 和内部 `/v1/responses`；无 error event |
| G-LS-02 | Responses | off | off | off | hit | 重复 G-LS-01 的同一 prompt 与 namespace | 返回 cache hit；会话新增 assistant；请求体不泄露凭据 |
| G-LS-03 | Responses | on | on | off | miss | 发送 `搜索今天一条科技新闻并用一句话总结` | 请求体包含 `web_search_preview`；UI 正常结束或受控显示上游错误；服务不崩溃 |
| G-LS-04 | Responses | on | off | on | miss | 选择 Gemini 图片模型和尺寸，发送 `生成一张简单蓝色方形图标` | 生成图片只渲染一次；图片 URL 可打开；请求记录不出现重复大图 payload |
| G-LS-05 | Responses | on | on | on | miss | 普通聊天 `你好，只回复文本` | Search/Image 均为可选能力；不得强制生成图片；UI 返回文本 |
| G-LS-06 | Responses | on | on | on | miss | 复现用户路径：先问候、询问身份、请求新闻，再发送 `做成图片` | 不再出现 `include_server_side_tool_invocations` 错误；如触发图片工具则只保存/展示一张对应图片；思考/工具过程不丢失 |
| G-LS-07 | Responses | off | on | on | miss | 发送 `把今天科技新闻做成简洁信息图` | 非流式也能保存图片/文本/错误；不会依赖 SSE 才正确 |
| G-LS-08 | Gemini | on/off | off/on | 不适用 | miss | 切到 Gemini interface，分别测普通聊天和 search prompt | `#studio` 调用内部 `/v1beta/models/...:generateContent` 或 `streamGenerateContent`；search on 时使用 Google Search；无 Responses 图片工具面板 |
| G-LS-09 | OpenAI Chat | on/off | off/on | 不适用 | miss | 切到 OpenAI Chat interface，测普通聊天和 search prompt | 内部 `/v1/chat/completions` 正常；search on 映射为当前项目支持的搜索字段；UI/日志完整 |
| G-LS-10 | Claude | on/off | off/on | 不适用 | miss | 切到 Claude interface，测普通聊天和 search prompt | 内部 `/v1/messages` 正常或受控失败；失败时会话/请求记录/服务健康均正常 |

## P0 Local Studio - OpenAI-Compatible Provider

| ID | Interface | Stream | Search | Image Tool | Cache | 用户路径 | 通过标准 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| O-LS-01 | Models | 不适用 | 不适用 | 不适用 | 不适用 | 在 UI 新增 OpenAI-compatible provider，填 Base URL、从 key 文件读取 token，点击加载模型 | 模型列表加载；token 输入框不回显明文到日志；刷新后 provider 可恢复 |
| O-LS-02 | Responses | on/off | off | off | miss | 选择聊天模型，发送 `回复 ok` | 流式和非流式均可完成；请求记录目标为自定义 Base URL `/responses` |
| O-LS-03 | Responses | on | on | off | miss | 发送 `搜索今天一条科技新闻并总结` | 如果 provider 支持 search，应正常完成；如果返回 4xx，UI 只显示一个受控错误，服务端不得出现 `ResponseNotRead` 或 ASGI exception group |
| O-LS-04 | Responses | on/off | off | on | miss | 选择 `gpt-image-2`，尺寸 `1024x1024`，发送 `生成一个测试图标` | 支持图片的 provider 返回图片并渲染一次；不支持时优雅失败且服务健康保持 200 |
| O-LS-05 | Responses | on | on | on | miss | 普通聊天 `不要搜索，不要画图，只回复 ok` | 工具开启但不强制调用；不会错误生成图片 |
| O-LS-06 | OpenAI Chat | on/off | off/on | 不适用 | miss | 切到 OpenAI Chat interface，测普通聊天和 search toggle | 正常完成或 provider 兼容性错误受控显示；无未捕获后端异常 |
| O-LS-07 | Claude | on/off | off/on | 不适用 | miss | 如果 provider 支持 Messages，测普通聊天；否则保留负向兼容测试 | 成功或优雅失败；请求路径、状态码、错误文案记录完整 |
| O-LS-08 | Gemini | on/off | off/on | 不适用 | miss | 用户误选 Gemini interface 连接 OpenAI-compatible Base URL | UI 不崩溃；API 返回受控错误；会话错误可见；服务健康仍 200 |

## P1 Local Studio UI 状态与持久化

| ID | 路径 | 步骤 | 通过标准 |
| --- | --- | --- | --- |
| LS-UI-01 | Provider | 新增两个 OpenAI-compatible provider，切换后刷新页面 | 每个 provider 保留独立 Base URL、token、timeout、interface；当前 provider 恢复正确 |
| LS-UI-02 | Image Tool UI | Google provider 与 OpenAI-compatible provider 间切换 | Google 显示 Gemini 图片模型/尺寸；OpenAI 显示 `gpt-image-2` 和质量/背景/格式/压缩；无跨 provider 残留 |
| LS-UI-03 | Model Filtering | Responses 模式加载模型 | 聊天模型列表不出现 `gpt-image-*` 或 Gemini image-only 模型；图片模型出现在 Image Tool 选择器 |
| LS-UI-04 | Pending State | 发送流式请求时观察 pending 区域 | 显示当前 interface、model、stream、search/cache/image tool 摘要；结束后消失 |
| LS-UI-05 | Error State | 故意使用错误 token 或错误 Base URL | 错误显示在当前会话；输入框可继续使用；请求记录保存失败阶段 |
| LS-UI-06 | Attachments | 上传图片、文本/PDF 附件后发送 | 支持模型正常发送；不支持模型 UI 阻止或给出明确错误；附件预览和移除可用 |
| LS-UI-07 | Conversation | 新建、发送、刷新、恢复、重跑、重命名、单删、批量删除 | 历史列表、消息内容、图片、usage、错误和 cache 标记都能持久化并正确删除 |
| LS-UI-08 | Cache Namespace | 同 prompt 改变 namespace 后发送 | namespace 改变触发 miss；切回原 namespace 可 hit；日志/usage 与 UI 标记一致 |

## P1 基础模块回归

| ID | 入口 | 用户路径 | 通过标准 |
| --- | --- | --- | --- |
| BASE-CHAT-01 | `#chat` | 选择 OpenAI Responses、Gemini、Claude、OpenAI Chat 中至少两个模式，分别发送普通消息 | Playground 仍独立可用；Local Studio provider 设置不影响 Playground |
| BASE-CHAT-02 | `#chat` | 开启 Search 发送新闻类 prompt | 搜索能力仍按 Playground 语义工作；请求记录显示基础 `/v1` 或 `/v1beta` 路径 |
| BASE-IMG-01 | `#images` | 选择图片模型，生成一张 1:1 图片 | 独立图片生成页可用；生成图片保存到 generated-images；不依赖 Local Studio Image Tool |
| BASE-IMG-02 | `#images` | 上传历史图/参考图后做编辑或重试 | 参考图、基图、历史会话、下载/删除不回归 |
| BASE-REQ-01 | `#requests` | 查看、复制、导出、批量删除多组请求 | 对 Local Studio 和基础模块请求都能按 group 展示完整 lifecycle |
| BASE-ACC-01 | `#accounts` | 列出账号、健康检查、切换/激活账号、查看池状态 | 账号管理线仍独立工作；不会因 Local Studio provider 封装被隐藏或破坏 |

## P1 API 级直接验证

| ID | API | Payload | 通过标准 |
| --- | --- | --- | --- |
| API-LS-01 | `POST /api/local-studio/models` | Google provider + Responses/Gemini/OpenAI/Claude mode | 返回 chat models 和 image models；Google provider 不需要 Authorization |
| API-LS-02 | `POST /api/local-studio/models` | OpenAI-compatible provider + token | Authorization 发送到上游但 request log 脱敏 |
| API-LS-03 | `POST /api/local-studio/chat` | Google Responses + `search=false` + `image_tool_enabled=false` | 文本回复，conversation JSON 保存 user/assistant |
| API-LS-04 | `POST /api/local-studio/chat` | Google Responses + `search=true` + `image_tool_enabled=true` + image prompt | 覆盖 Gemini 图片工具故障路径；无 `include_server_side_tool_invocations` 错误 |
| API-LS-05 | `POST /api/local-studio/chat` | OpenAI Responses stream + `search=true` | 覆盖 OpenAI search 4xx 流式路径；无 `ResponseNotRead` |
| API-LS-06 | `GET /api/local-studio/assets/{path}` | 打开 Local Studio 生成图 URL | 返回图片 MIME；路径穿越返回 400/404 |
| API-REQ-01 | `/request-logs/*` | status、list、detail、export、delete | lifecycle 完整且导出 JSON 可解析 |
| API-BASE-01 | `/v1/chat/completions`、`/v1/responses`、`/v1/messages`、`/v1/images/generations` | 基础 API smoke | 基础兼容 API 不因 Local Studio 改造回归 |

## Bug 专项断言

### BUG-GEMINI-IMAGE-TOOL-01

复现链路：Google AI Studio provider，Local Studio Responses interface，stream on，search on，image tool on，历史中先产生新闻回答，再发送 `做成图片`。

必须断言：

* 浏览器没有未捕获 console error。
* 客户端 SSE 不包含 `event: error`，或如果上游确实失败，UI 只显示受控错误且会话保存该错误。
* 服务端日志不包含 ASGI exception。
* 请求记录 upstream response 不包含 `Please enable tool_config.include_server_side_tool_invocations`。
* 最终如果有图片，UI 和 conversation JSON 中同一张图片只出现一次。
* Reasoning/tool details 有可见入口或被保存，不能只剩 `Generated image` 且完全丢失过程。

### BUG-OPENAI-SEARCH-STREAM-01

复现链路：OpenAI-compatible provider，Local Studio Responses interface，stream on，search on，上游返回 HTTP 400。

必须断言：

* `/api/local-studio/chat` 返回一条格式正确的 SSE error 事件，不断开成浏览器网络错误。
* UI 当前会话显示错误，输入框恢复可用。
* 服务端 stderr 不包含 `httpx.ResponseNotRead`、`ExceptionGroup`、`Exception in ASGI application`。
* 请求记录包含 upstream 400 response body 和 client response，不缺阶段。
* 故障后 `/api/local-studio/health`、`/request-logs/status` 仍返回 200。

## 执行顺序

1. 启动 WSL 临时环境，确认 health/model/account 预检通过。
2. 开启 request logs。
3. 执行 API 级 P0 smoke，先验证 provider/model/chat/search/image 基础链路。
4. 执行浏览器 P0 Local Studio 矩阵，覆盖两个 bug 专项。
5. 执行 P1 UI 状态、会话、cache、附件和基础模块回归。
6. 导出必要请求记录和截图到本次临时目录的 `artifacts/`，检查脱敏后再附到人工报告；不要提交。
7. 清理临时服务、浏览器进程和临时数据目录。

## 通过门禁

* P0 全部通过；P1 不通过项必须有明确 bug 编号、日志、截图和请求记录 group id。
* 没有未捕获 ASGI 异常、浏览器 console error 或 Playwright 页面崩溃。
* 所有成功路径都能在 UI 中看到用户可理解结果，并在 API/request log 中看到对应请求。
* 所有失败路径都是受控失败，且服务继续可用。
* Request log、截图、导出文件不包含真实 OpenAI token、Google cookie、Authorization header 明文或账号 storage state。
* Local Studio 的 provider 封装不影响 Playground、图片生成、请求记录和账号管理独立入口。

## 建议输出物

每次完整系统测试完成后，在临时目录保存：

* `artifacts/summary.md`：执行环境、git commit、服务端口、通过/失败列表。
* `artifacts/api-results.json`：每个 API 用例的状态码、耗时、request log group id、脱敏错误摘要。
* `artifacts/ui-results.json`：每个 UI 用例的页面、断言、截图路径、console/network 摘要。
* `artifacts/screenshots/`：关键 UI 成功/失败截图。
* `artifacts/server.log`：服务端日志，检查后确认无 secrets。

这些输出物用于人工验收或 bug 附件，不进入仓库。
