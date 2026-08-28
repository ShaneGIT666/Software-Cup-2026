# 修改日志索引

| 变更标识 | 日期 | 主责模块 | 记录状态（不等于功能状态） | 简述 | 日志 |
| --- | --- | --- | --- | --- | --- |
| `2026-08-13-001-change-log` | 2026-08-13 | M7 | 变更已结束 | 建立仓库内本地修改日志机制 | [记录](2026-08-13-001-change-log.md) |
| `2026-08-13-002-auth-entry-exception` | 2026-08-13 | M1 | 变更已结束 | 明确认证例外中的本地登录入口 | [记录](2026-08-13-002-auth-entry-exception.md) |
| `2026-08-13-003-m0-m1-prerequisites` | 2026-08-13 | M0 | 变更已结束 | 搭建 M1 所需的公共契约、装配和数据前置代码 | [记录](2026-08-13-003-m0-m1-prerequisites.md) |
| `2026-08-13-004-m1-design` | 2026-08-13 | M1 | 变更已结束 | 复核前置并形成 M1 身份与审计设计方案 | [记录](2026-08-13-004-m1-design.md) |
| `2026-08-13-005-m1-contract-gates` | 2026-08-13 | M1 | 变更已结束 | 记录身份错误码、审计权限与 Cookie 设计门槛 | [记录](2026-08-13-005-m1-contract-gates.md) |
| `2026-08-13-006-m1-core-foundation` | 2026-08-13 | M1 | 变更已结束 | 搭建身份、会话、RBAC 与不可变审计基础代码 | [记录](2026-08-13-006-m1-core-foundation.md) |
| `2026-08-13-007-m1-completion-audit` | 2026-08-13 | M1 | 变更已结束 | 对照 SRS/设计复核代码进度与后续冲突 | [记录](2026-08-13-007-m1-completion-audit.md) |
| `2026-08-13-008-m0-http-concurrency-contract` | 2026-08-13 | M0 | 变更已结束 | 冻结游标、If-Match/ETag 与可信来源公共契约 | [记录](2026-08-13-008-m0-http-concurrency-contract.md) |
| `2026-08-13-009-m1-identity-persistence` | 2026-08-13 | M1 | 变更已结束 | 搭建身份持久化、登录限流和请求依赖接缝代码 | [记录](2026-08-13-009-m1-identity-persistence.md) |
| `2026-08-13-010-module-progress-audit` | 2026-08-13 | M7 | 变更已结束 | 更正功能完成状态，记录冲突并冻结后续接口计划 | [记录](2026-08-13-010-module-progress-audit.md) |
| `2026-08-13-011-m1-local-identity-http` | 2026-08-13 | M1 | 变更已结束 | 搭建本地身份、用户与审计 HTTP；真实 PostgreSQL 尚未验证 | [记录](2026-08-13-011-m1-local-identity-http.md) |
| `2026-08-13-012-m0-m1-deployment-audit` | 2026-08-13 | M7 | 变更已结束 | 复核 M0/M1 部署并冻结后续无冲突接入方案 | [记录](2026-08-13-012-m0-m1-deployment-audit.md) |
| `2026-08-14-013-m0-m1-public-integration-gates` | 2026-08-14 | M0 | 变更已结束 | 修正 M0/M1 公共接入门槛并冻结后续模块边界 | [记录](2026-08-14-013-m0-m1-public-integration-gates.md) |
| `2026-08-14-014-readme-baseline-alignment` | 2026-08-14 | M7 | 变更已结束 | 对齐根 README 与当前产品、开发和部署基线 | [记录](2026-08-14-014-readme-baseline-alignment.md) |
| `2026-08-14-015-historical-document-baseline-boundary` | 2026-08-14 | M7 | 变更已结束 | 收紧历史文档与现行基线、状态和阅读优先级边界 | [记录](2026-08-14-015-historical-document-baseline-boundary.md) |
| `2026-08-17-016-stage0-contract-alignment` | 2026-08-17 | M7 | 变更已结束 | 统一现行状态、readiness、outbox 和 M1 追踪契约 | [记录](2026-08-17-016-stage0-contract-alignment.md) |
| `2026-08-17-017-m0-foundation-hardening` | 2026-08-17 | M0 | 变更已结束 | 加固 M0 环境、脱敏异常、CORS 和 readiness | [记录](2026-08-17-017-m0-foundation-hardening.md) |
| `2026-08-17-018-current-document-baseline-closure` | 2026-08-17 | M7 | 变更已结束 | 收口现行文档、需求追踪、事件目录和后续模块边界 | [记录](2026-08-17-018-current-document-baseline-closure.md) |
| `2026-08-17-019-d1-2-production-contract-closure` | 2026-08-17 | M1 | 变更已结束 | 单元验证 v1 通用 500 OpenAPI 声明及 M1 受管主体/激活子边界；运行时外推见 020 更正 | [记录](2026-08-17-019-d1-2-production-contract-closure.md) |
| `2026-08-17-020-current-contract-document-correction` | 2026-08-17 | M7 | 变更已结束 | 按代码证据修正现行契约、追踪矩阵和文档冲突 | [记录](2026-08-17-020-current-contract-document-correction.md) |
| `2026-08-17-021-document-source-and-event-enablement-closure` | 2026-08-17 | M7 | 变更已结束 | 收口单一文档来源、历史边界和事件生产启用门禁 | [记录](2026-08-17-021-document-source-and-event-enablement-closure.md) |
| `2026-08-28-022-follow-up-development-plan` | 2026-08-28 | M7 | 变更已结束 | 基于当前代码和现行契约形成 M0～M7 后续实施路线图 | [记录](2026-08-28-022-follow-up-development-plan.md) |
| `2026-08-29-023-m0-p0-contract-closure` | 2026-08-29 | M0 | 变更已结束 | 单元关闭 v1 错误/日志、具体 DTO/OpenAPI 与无 ORM ClaimPort 契约缺口 | [记录](2026-08-29-023-m0-p0-contract-closure.md) |

历史日志正文中的“已完成”只表示对应修改记录已结束，不代表需求功能完成；索引已统一改用“变更已结束”，第 010 号起日志正文使用“记录状态 + 功能验证状态”双字段，第 018 号起新增“状态对象 + 规范来源影响 + 状态与证据”。新增记录前先检查变更标识、受影响模块和关联记录，避免为同一目标重复建档或产生相互矛盾的设计。
