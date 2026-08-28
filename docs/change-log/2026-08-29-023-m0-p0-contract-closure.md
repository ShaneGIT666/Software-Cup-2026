# 关闭 M0 P0 公共安全、DTO 与 ClaimPort 契约缺口

- 变更标识：`2026-08-29-023-m0-p0-contract-closure`
- 日期：`2026-08-29`
- 记录状态：`变更已结束`
- 状态对象：`M0 v1 错误/普通日志脱敏、当前 15 个 v1 操作的具体 DTO/OpenAPI、OutboxClaimPort 公共契约`
- 功能验证状态：`单元已验证`
- 所属模块：`M0`；协作模块：`M1、M4、M6、M7`
- 需求追踪：`DATA-02、API-02、API-05、NFR-REL-02、NFR-SEC-04、NFR-OBS-01、NFR-MNT-04`
- 关联记录：`2026-08-17-017-m0-foundation-hardening`、`2026-08-17-019-d1-2-production-contract-closure`、`2026-08-17-020-current-contract-document-correction`、`2026-08-28-022-follow-up-development-plan`
- 规范来源影响：`动态状态、公共契约`

## 改动内容

- 统一 v1 显式 `HTTPException`/`AppError` 与未捕获 5xx 的公共脱敏边界；仅固定 `DEPENDENCY_UNAVAILABLE/503` 保留 503，其他外部 5xx 固定为 `INTERNAL_ERROR/500`。普通 4xx 不再透传内部 details。
- 请求校验错误只返回有界 `loc/type`、固定公共消息和白名单 `ctx.limit_value`，不回显请求 input/body、原 validator 消息或任意上下文。
- 普通日志改为在结构化 `extra` 合并后执行进程级白名单/失败关闭，覆盖异常/堆栈、多词请求体/载荷/headers、Cookie、令牌、连接串及 Windows/Unix 绝对路径；现存先拼接异常原文的日志调用改为固定事件。
- 为当前 15 个 v1 操作增加命名的具体 success DTO；用户与审计分页分别绑定具体 item DTO；default、422、500 和 readiness 503 使用封闭错误模型。身份/分页 `JSONResponse` 在序列化前使用相同具体 DTO 校验。
- 新增 OpenAPI consumer-contract 测试，精确枚举 15 个操作并递归拒绝空 schema、自由 object 和泛型分页项。未手写 TypeScript DTO；M6 后续只从该 OpenAPI 输入选择一个生成器，避免重复类型源。
- 在无 ORM 副作用的 `core/ports` 冻结 `OutboxClaimPort` 及不可变值对象，覆盖 claim、lease/heartbeat、success、retry、dead-letter、replay、fencing、失败状态和 operation-id 幂等；未实现数据库适配器、Worker 或事件消费者。
- 更新现行追踪矩阵、M0 公共契约、后续开发方案及相关稳定接入计划，把下一实施顺序推进到 M1 P1、D2 PostgreSQL 与 M0/M4 适配器协作。

## 文件与数据影响

- `backend/app/core/{contracts,log_sanitization,server_error_sanitization,validation_sanitization}.py`、`backend/app/core/ports/`；新增/修改公共模型、脱敏边界与 ClaimPort。
- `backend/app/api/v1/`、`backend/app/main.py`、`backend/app/domains/identity/http_responses.py`；修改 v1 路由响应模型、错误声明与运行时校验。
- `backend/app/{knowledge,llm_adapter,multimodal_adapter,ocr_adapter,vector_store}.py`；仅将可能先拼接异常原文的普通日志改为固定事件，不改变领域返回值或持久化行为。
- `tests/test_module0_error_sanitization.py`、`tests/test_module0_v1_response_contracts.py`、`tests/test_module0_outbox_claim.py` 及既有相关 M0/M1 测试；新增/更新回归和契约验证。
- `backend/README.md`、`docs/design/{m0-public-contract,follow-up-development-plan,module-build-progress-and-interface-plan,m0-m1-deployment-readiness-plan}.md`、`docs/requirements/current-traceability-matrix.md`；更新代码入口、公共边界、无冲突顺序和动态状态。
- 数据库表、Alembic revision、领域事件生命周期、API 路径、配置项：无。OpenAPI response schema 为公共契约变更。

## 依赖与冲突检查

- 已检查：父提交 `fe7d5df`、修改日志索引与记录 017/019/020/022、SRS、现行追踪矩阵、M0 公共契约、领域事件目录、M0/M1 部署接入方案、模块接口计划、当前 15 个 v1 operation、`alembic heads` 和 M4/M6 预留所有权。
- 结论：错误/日志/DTO 只修改 M0 公共面；ClaimPort 位于 `core/ports`，干净进程导入不加载 SQLAlchemy，M4 不需依赖 M0 ORM。没有实现 M4 Worker、创建迁移、生产事件或手写前端 DTO，因此不与 P1、M4 适配器或 M6 生成客户端重复。
- 状态与证据：当前代码边界具有进程内/契约测试，故对应状态对象为“单元已验证”。没有真实 PostgreSQL、代理、日志采集、Worker、多进程并发、生成客户端或浏览器证据，不提升 M0 整体为“集成已验证”或“已完成”。

## 验证与回滚

- 验证：`python -m pytest -q`：`309 passed, 25 skipped`；skip 不计作集成证据。
- 验证：`npm run build`：通过；存在既有第三方 PURE 注释和大 chunk 非阻断警告，未作为 P0 功能失败。
- 验证：`alembic heads`：`20260817_0006 (head)`；本次无迁移。
- 验证：`python -m compileall -q backend/app`、干净进程 ClaimPort 无 SQLAlchemy 导入测试、OpenAPI 15/15 具体响应检查、`git diff --check`：通过。
- 回滚：恢复本记录列出的修改文件并删除新增 M0 模块/测试/本记录及索引行；不涉及数据库降级、数据恢复或事件补偿。

## 后续开发提示

- 下一代码门禁是 M1 的 typed actor 审计桥接、metadata DTO、reviewer capacity、权限补齐和服务主体 readiness；其后由 M7 在专用 PostgreSQL 16 关闭 D2。
- M0 后续拥有 ClaimPort 的数据库适配器和迁移，M4 只经 `app.core.ports` 编排 Worker；必须在 PostgreSQL 验证数据库时钟、原子 claim、fencing、retry/dead-letter/replay、重启恢复和多 Worker 并发。
- M6 必须锁定单一 OpenAPI TypeScript 生成器并提交生成产物/类型消费测试；不得复制 Python DTO 或手写第二套接口。事件仍处于目录现有状态，不能因 ClaimPort 契约冻结而启用生产发布。
