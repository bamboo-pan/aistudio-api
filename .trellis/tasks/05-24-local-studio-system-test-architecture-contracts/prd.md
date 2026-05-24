# 完善 Local Studio 系统测试计划架构契约覆盖

## Goal

将 `LOCAL_STUDIO_WEB_REAL_SYSTEM_TEST_PLAN.md` 从真实链路回归计划增强为能验证 `ARCHITECTURE.md` 关键承诺的架构契约测试计划，避免 OpenAI Responses reasoning 缺失这类问题被泛泛的维度覆盖掩盖。

## Requirements

* 增加一组可复用的架构不变量断言，覆盖 provider 路由隔离、interface 语义隔离、工具可选语义、中间过程保留、cache 隔离、基础模块独立性、错误一致性、敏感信息边界、持久化恢复和前端状态机。
* 强化 OpenAI-compatible provider 的 Responses reasoning 覆盖，明确要求请求体、API 响应、UI、conversation JSON、刷新恢复和 request log 都能保留或解释 reasoning summary / tool details。
* 强化 cache 测试 oracle，要求 provider、interface、model、tools、reasoning、attachments、token hash 和 namespace 改变时不会串线命中。
* 强化 provider 管理和基础模块独立性测试，确保 Local Studio 的错误 provider 配置不会影响 Playground、图片生成和账号管理基础入口。
* 强化 UI 状态机测试，覆盖 idle、pending、streaming、tool-running、completed、error、retry 等状态不残留、不丢输入、不产生空 assistant 卡片。
* 保持测试计划中文风格和现有表格结构，不引入实现代码变更。

## Acceptance Criteria

* [ ] 测试计划新增“架构契约断言”类章节，并能直接映射 `ARCHITECTURE.md` 的主要节点和边界。
* [ ] OpenAI Responses reasoning 缺失问题有明确 P0/P1/API/Bug 专项覆盖，不再只依赖泛化 `Reasoning` 维度。
* [ ] Cache、provider、interface、tool、reasoning、attachment 的隔离关系有可执行判定标准。
* [ ] 基础业务线独立性和 request log 横向服务的断言更严格。
* [ ] 文档结构清晰，和原计划术语一致，没有把真实密钥、日志或测试产物写入仓库。

## Definition of Done

* Trellis task files and updated test plan are committed on a feature branch.
* Documentation diff is reviewed for consistency and no accidental secrets.
* Because this is documentation-only, no WSL real system test is required for this task.

## Technical Approach

* Edit `LOCAL_STUDIO_WEB_REAL_SYSTEM_TEST_PLAN.md`, Trellis task metadata, and the backend quality spec if this work establishes a reusable system-test-plan convention.
* Add reusable architecture invariants near coverage/combination rules so each matrix case can inherit them.
* Add targeted rows for OpenAI Responses reasoning in the OpenAI P0 table, UI persistence table, API table, and Bug assertions.
* Tighten existing rows where a small wording change is enough instead of duplicating cases.

## Decision (ADR-lite)

**Context**: The existing plan covers many real paths and known bugs, but a missing OpenAI Responses reasoning display can still slip through because several requirements are provider-agnostic and result-focused.

**Decision**: Treat architecture promises as explicit test oracles and add provider-specific reasoning/cache/state assertions rather than only adding one more isolated test row.

**Consequences**: The plan becomes longer, but future regressions are easier to classify as contract failures instead of ambiguous UI/API behavior.

## Out of Scope

* Implementing or fixing Local Studio runtime behavior.
* Running the full real WSL system test suite.
* Adding automated Playwright/API scripts for the plan.
* Updating `ARCHITECTURE.md` unless the test plan exposes a contradiction.

## Technical Notes

* `ARCHITECTURE.md` defines Local Studio as a higher-level orchestrator while Playground, image generation, request logs, and account management remain independently usable.
* `ARCHITECTURE.md` explicitly states search/image tools are optional capabilities, not forced calls.
* The current test plan already contains strong P0 coverage for Google image tool and OpenAI search bugs, so this task should preserve those while adding cross-cutting contract assertions.