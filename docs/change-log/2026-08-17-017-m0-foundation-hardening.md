# M0 公共底座失败关闭与 readiness 加固

- 变更标识：`2026-08-17-017-m0-foundation-hardening`
- 日期：`2026-08-17`
- 记录状态：`变更已结束`（只描述本次修改记录，不表示需求功能完成）
- 功能验证状态：`单元已验证`
- 所属模块：`M0`；协作模块：`M1、M7`
- 需求追踪：`API-02、API-05、FR-OPS-01、FR-OPS-02、NFR-REL-01、NFR-SEC-04、NFR-OBS-01`
- 关联记录：`2026-08-14-013-m0-m1-public-integration-gates`、`2026-08-17-016-stage0-contract-alignment`

## 改动内容

- 将 `APP_ENV` 收紧为 `development|test|production`；显式空值、空白值或拼写错误一律失败关闭，只有未设置时使用开发默认。
- 新增 M0 `INTERNAL_ERROR` 错误码和全局未捕获异常处理；v1 返回固定脱敏 500 信封与 request ID，服务端日志保留异常追踪。旧表面继续使用原有响应形状，但同样不泄露异常文本。
- CORS 响应暴露头增加 `ETag`，保留 `X-Request-ID`，为后续 M6 跨域 `If-Match` 客户端提供公共契约。
- 将 readiness 任意 `Mapping` 替换为不可变 `ReadinessDetails`，对 `configured`、`dialect`、`mode`、`latencyMs` 和 `violations` 的值执行 M0 白名单/类型校验，并对 reason 中的 URL、连接串、绝对路径、换行和敏感标记进行通用替换。
- readiness 固定注册表补齐 knowledge、devices 和 workflows，现覆盖 identity、documents、knowledge、devices、workflows、workers、indexing 和 rag；公开 `evaluate_foundation_readiness()` 作为统一基础配置预检端口。
- M1 identity contributor 改用 `ReadinessDetails(mode=...)`，未导入 M1 私有 ORM/Repository，未改变 M1 认证语义。
- 为上述缺陷增加环境空值/拼写、脱敏 500、CORS 响应头、readiness 注册完整性、强类型白名单和敏感 reason 回归测试。

## 文件与数据影响

- `backend/app/core/config.py`、`cors.py`、`error_codes.py`、`readiness.py`；修改。
- `backend/app/main.py`；新增全局未捕获异常处理，未新增业务路由。
- `backend/app/domains/identity/readiness.py`；修改 M0 公共详情 DTO 消费方式。
- `tests/test_module0_foundation.py`、`test_module0_m1_prerequisites.py`、`test_module0_readiness.py`；新增/更新回归测试。
- `README.md`、`backend/README.md`、SRS、M0/M1 部署就绪计划、M1 设计和模块进度计划；更新当前代码与验证证据。
- 对外 API：未新增路径；未捕获 v1 异常新增稳定 `INTERNAL_ERROR/500`，CORS 新增暴露 `ETag`，readiness 公共详情收紧为强类型白名单。
- 配置：`APP_ENV` 未设置时仍默认 `development`；显式无效值从“可继续启动”变为启动/装配失败。
- 数据库与迁移：无结构变更，未新增 Alembic revision；单一 head 仍为 `20260814_0005`。

## 依赖与冲突检查

- 已检查：`docs/change-log/INDEX.md`、记录 013～016、SRS、M0 公共契约、M1 设计、模块进度计划、M0/M1 部署就绪计划、当前 v1 路由/异常/CORS/readiness 代码与消费者，以及 migration head。
- 结论：复用现有 request ID、v1 信封、配置、领域发现和 M1 contributor，未新建第二套预检/异常/CORS 机制，未改变旧 `/api` 路由或历史迁移。真实 PostgreSQL、代理、跨域浏览器和 Windows Service 仍是未关闭集成门槛。

## 验证与回滚

- 定向回归：`.\backend\.venv\Scripts\python.exe -m pytest tests\test_module0_foundation.py tests\test_module0_readiness.py tests\test_module0_m1_prerequisites.py -q`，`49 passed in 0.82s`。
- 全量回归：`.\backend\.venv\Scripts\python.exe -m pytest -q`，`259 passed, 25 skipped in 17.68s`；3 项真实 PostgreSQL 和 22 项外部手册测试跳过，不计为集成成功。
- 前端兼容：从 `frontend/` 执行 `npm run build`，构建成功；主 JavaScript `1,052.46 kB`，仍有大 chunk 警告。
- 装配：仓库根 `backend.app` 和 `backend/` 目录 `app` 两种导入路径均发现 15 个 v1 操作（14 个唯一路径）；`.\.venv\Scripts\alembic.exe heads` 返回单一 `20260814_0005 (head)`。
- 静态检查：`python -m compileall -q backend\app` 和 `git diff --check` 成功；排除 `.venv`/`node_modules`/`.git` 后检查 119 份工作区 Markdown，相对链接 0 断链。
- 验证环境：Windows 10 Home China 25H2（NT `10.0.26200.0`）、Python `3.12.7`、Node `22.17.1`、npm `10.9.2`；`APP_DATABASE_URL` 未设置，未发现 `psql`/PostgreSQL 服务。
- 回滚：恢复上述 M0/M1 代码、测试和阶段 1 证据文档；无数据库降级或运行数据恢复步骤。回滚 `APP_ENV` 和脱敏 500 会重新引入已记录安全风险，只能通过新变更记录执行。

## 后续开发提示

- M2～M5 contributor 只能使用 `ReadinessProbe` + `ReadinessDetails`；新增 detail 字段或值前必须修改 M0 契约与消费者测试，不得恢复任意映射。
- M7 的 Windows/Linux 预检必须复用 `get_settings()`、`evaluate_foundation_readiness()` 和 `/api/v1/health/ready`，不得复制一套环境枚举或脱敏规则。
- M6 可依赖 CORS 暴露 `ETag`，但在真实跨域浏览器上完成读取与 `If-Match` 回传前，仍不能标记为“集成已验证”。
- M1 bootstrap 受控系统主体与独立 CLI 操作标识仍属于后续 M1 修正，本记录未提前实现。
