# 前端账号管理功能

## Goal

在现有 Web UI 的账号管理页面补齐常用账号操作，让用户可以在浏览器里完成查看、登录、激活、删除、重命名和轮询配置，而不用回到命令行调用 `/accounts` API。

## What I Already Know

* 用户希望“在前端里加上账号管理功能”。
* 现有前端是静态 Alpine.js 应用，主要文件为 `src/aistudio_api/static/index.html`、`src/aistudio_api/static/app.js`、`src/aistudio_api/static/style.css`。
* 现有导航已包含“账号管理”页面。
* 当前账号页已支持：读取账号列表、读取活跃账号、登录新账号、激活账号、保存轮询模式、强制切换账号、显示基础账号统计。
* 后端已有账号接口：`GET /accounts`、`GET /accounts/active`、`POST /accounts/login/start`、`GET /accounts/login/status/{session_id}`、`POST /accounts/{account_id}/activate`、`DELETE /accounts/{account_id}`、`PUT /accounts/{account_id}`。
* 静态前端没有构建步骤；变更集中在 HTML/CSS/JS。

## Assumptions

* 本任务优先补齐现有账号页的功能缺口，而不是重做整个 UI。
* 删除账号需要前端确认，避免误删 auth state。
* 登录流程可通过现有后端接口启动，并在前端展示登录会话状态。

## Open Questions

* 等待用户确认完整 PRD 后进入实现。

## Requirements

* 账号管理页展示账号列表、当前激活账号、轮询统计和可用操作。
* 用户能从前端删除账号。
* 删除账号前展示确认步骤，确认文案应能让用户识别将被删除的账号。
* 用户能从前端重命名账号。
* 用户点击“登录账号”后，前端展示登录流程已启动，并轮询或查询登录状态，展示 pending / completed / failed 结果。
* 删除失败、激活失败、登录启动失败等操作需要有明确反馈。
* 无活跃账号、账号列表为空、接口请求失败时，页面仍能显示可理解状态，不应因为 `/accounts/active` 返回 404 而清空整个账号列表。
* 完成删除、重命名、激活、登录成功后，刷新账号列表、活跃账号和轮询信息。

## Acceptance Criteria

* [ ] 账号列表中每个账号提供删除操作。
* [ ] 删除账号前有确认步骤。
* [ ] 删除成功后账号列表、活跃账号和轮询信息刷新。
* [ ] 删除失败时展示错误提示。
* [ ] 页面在无账号或 `/accounts/active` 返回 404 时仍正常显示。
* [ ] 账号列表中每个账号提供重命名操作，成功后刷新列表。
* [ ] 登录账号操作展示当前登录 session 的状态，并在登录完成后刷新账号列表。
* [ ] 激活、删除、重命名等按钮在请求过程中避免重复提交。

## Definition of Done

* 前端行为符合现有 Alpine.js 风格。
* 样式与现有控制台 UI 一致，移动端不溢出。
* 至少运行相关测试或可用的静态/手动验证。
* 如发现新项目约定，评估是否更新 `.trellis/spec/`。

## Technical Approach

延续现有静态 Alpine.js 架构，在 `app.js` 中增加账号操作状态、删除/重命名/登录状态方法；在 `index.html` 的账号页补齐操作按钮、确认/编辑 UI 和状态展示；在 `style.css` 中补充小型表单、危险按钮、状态提示等样式。后端账号接口已存在，本任务不新增后端能力。

## Decision (ADR-lite)

**Context**: 用户希望直接在前端完成账号管理，当前页面已有账号页雏形但缺少删除、重命名和登录状态反馈。

**Decision**: 选择“完整账号管理版”：删除 + 重命名 + 登录状态提示 + 无活跃账号/请求失败时页面不坏。

**Consequences**: 变更保持在静态前端内，交付速度快；复杂弹窗系统暂不引入，确认和编辑交互应保持轻量并与现有 UI 风格一致。

## Out of Scope

* 后端账号接口新增能力。
* OAuth/Google 登录流程重构。
* 新前端框架或构建系统。
* 账号导入/导出。
* 批量删除或批量编辑。

## Technical Notes

* `src/aistudio_api/static/app.js` 已有 `addAccount()`、`activateAccount()`、`loadAccounts()`、`loadRotation()`，适合继续扩展。
* `src/aistudio_api/static/index.html` 账号表当前只有“手动激活”按钮，需要增加删除/重命名等操作位。
* `loadAccounts()` 当前将 `/accounts` 与 `/accounts/active` 放在同一个 `Promise.all`，如果没有活跃账号导致 `/accounts/active` 404，可能会丢掉账号列表更新；这是账号页健壮性需要处理的点。
* `src/aistudio_api/api/routes_accounts.py` 已提供删除和更新名称接口。
