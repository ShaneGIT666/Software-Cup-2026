# 冻结 M0 游标、并发条件与可信来源公共契约

- 变更标识：`2026-08-13-008-m0-http-concurrency-contract`
- 日期：`2026-08-13`
- 状态：`已完成`
- 所属模块：`M0`；协作模块：`M1`、`M2`、`M3`
- 需求追踪：`AUTH-10`、`API-02`～`API-04`、SRS 14.2～14.5
- 关联记录：`2026-08-13-003-m0-m1-prerequisites`、`2026-08-13-007-m1-completion-audit`

## 改动内容

- 增加版本化不透明 cursor codec，统一损坏游标错误，防止 M1/M2/M3 各自定义分页编码。
- 冻结强 ETag/`If-Match` 格式和缺失、非法、过期三类响应语义。
- 增加独立于 CORS 的服务端可信浏览器来源校验，供匿名登录和 Cookie 写接口复用。

## 文件与数据影响

- `backend/app/core/pagination.py`、`concurrency.py`、`trusted_origins.py`；新增：M0 公共 HTTP 接缝。
- `backend/app/core/error_codes.py`、`core/__init__.py`；修改：登记公共错误码和导出接口。
- `tests/test_module0_m1_prerequisites.py`、`docs/design/m0-public-contract.md`；修改：契约测试和冻结说明。
- API 字段不变；新增错误码 `INVALID_CURSOR`、`PRECONDITION_REQUIRED`、`INVALID_PRECONDITION`、`TRUSTED_ORIGIN_REQUIRED`；数据库、迁移、事件和配置键无变更。

## 依赖与冲突检查

- 已检查：M0 分页信封、CORS、错误码、M1 第 007 号审计、SRS API/AUTH 规则及仓库内 cursor/ETag/Origin 实现。
- 结论：此前仅冻结字段名和 `VERSION_CONFLICT`，不存在可复用 codec、条件头解析或服务端来源检查；本次补齐公共接缝，没有重复实现或修改领域表。游标不承担授权，领域 Repository 仍须逐页重施权限过滤。

## 验证与回滚

- 验证：M0 聚焦测试 `33 passed`；纳入 M1 本批次后的完整测试 `216 passed, 22 skipped`；双包路径导入和 Alembic 单一 head 验证通过，`git diff --check` 通过。
- 回滚：删除三个公共帮助文件及四个错误码，恢复公共契约和测试；无数据库或运行数据影响。M1/M2/M3 一旦消费该契约后不得单独回滚。

## 后续开发提示

- M1/M2/M3 必须复用该 codec 和条件头格式，不得创建不同的 Base64 信封、裸版本号或 Origin 比较逻辑。响应 ETag/no-store 由各领域路由在响应帮助层统一设置。

## 状态更正（2026-08-13-010）

- 本记录中的“已完成”表示第 008 号公共帮助代码和文档变更已经结束；只验证了单元/进程内契约，不表示使用这些帮助的真实业务接口已经完成或通过验收。
- M0 在 M1 认证路由前仍需交付独立短事务、统一数据库 503 映射和可信客户端地址端口，见 `2026-08-13-010-module-progress-audit` 与 M0 公共契约第 6 节。
