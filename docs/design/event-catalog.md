# 现行领域事件目录

> 文档性质：具体领域事件、版本、生命周期和生产者/消费者登记的唯一事实源<br>
> 主责：M0 契约治理；事件生产者与 M4 消费者共同评审<br>
> 功能实现状态、测试证据和未关闭问题只在[现行需求追踪矩阵](../requirements/current-traceability-matrix.md)维护。

## 1. 作用与生命周期

SRS 只定义何时必须可靠发布事件，M0 公共契约只定义 outbox append 和后续 claim 公共端口；具体事件只能在本目录增加、冻结、升级或废弃。新增事件通常不重复修改 README、SRS 或模块设计文档。

事件生命周期与功能状态相互独立：

| 生命周期 | 含义 | 生产约束 |
| --- | --- | --- |
| 提议 | 名称、生产者或预期用途可用于设计与版本化 Mock，但契约条件尚未闭合 | 禁止生产代码发布 |
| 已冻结 | 生产者、实际消费者、payload、事务触发点、幂等、顺序/重复、失败恢复、权限/隐私和兼容测试均已登记 | 生产者可按冻结版本发布；实现/集成状态仍见追踪矩阵 |
| 已废弃 | 已完成消费者迁移、积压处理、重放工具和回滚安排 | 新生产者禁止发布；保留期内消费者按迁移方案处理 |

“预期消费者”只是设计意向，不是“已登记实际消费者”。实际消费者登记必须指向明确的生产 consumer ID、所有模块/处理器公共端口、可定位的生产 handler 实现、去重键、重放规则和失败责任人；只有 Mock、接口草稿或未来模块名不算实际消费者。

## 2. append 输入与持久化/投递 envelope

生产者在拥有领域事务的 Session 中调用 M0 `OutboxWriter.append()`。append 调用输入固定为：

| `OutboxEventInput` 字段 | 规则 |
| --- | --- |
| `event_type` | `<Domain><Fact>.v<major>`；major 改变表示不兼容升级 |
| `aggregate_type` | 稳定领域聚合类型 |
| `aggregate_id` | 稳定聚合 ID，不使用路径或显示名 |
| `version_id` | 产生事实的业务版本；不得以当前时间伪造 |
| `request_id` | 原始请求或受控任务的 request ID |
| `occurred_at` | UTC、有时区时间 |
| `payload` | 事件专用封闭 DTO 的序列化结果；禁止任意请求体 |

`OutboxEventInput` 不包含 `event_id`。Writer 在持久化时生成稳定唯一 ID，并返回 `OutboxAppendResult(event_id)`。持久化记录和投递 envelope 才由 `eventId` 加上对应的 `eventType`、`aggregateType`、`aggregateId`、`versionId`、`requestId`、`occurredAt` 和 `payload` 组成。生产者不得预先生成、复用或伪造 `eventId`。

Writer 只追加，不 commit/rollback，不返回 ORM。payload 禁止密钥、令牌、Cookie、密码、连接串、绝对路径、任意 metadata 和未筛选请求体；每个事件行必须链接自己的 schema 与正反例契约测试。

消费者只能通过 M0 另行冻结的 claim/lease/retry/replay 公共端口领取，不得导入或更新 `db.models.OutboxEvent`。本目录登记事件不自动冻结 ClaimPort；该端口的当前状态见追踪矩阵。

## 3. 主体、事务与 outbox 适用范围

| 操作类型 | 认证与审计主体 | outbox 规则 |
| --- | --- | --- |
| M2/M3/M5 可对外观察的领域事实变化 | 普通 HTTP 使用 `CurrentUser` 派生的交互 actor；异步延续使用 M1 受管服务 actor 并保留 initiator | 仅当对应事件“已冻结”且登记实际消费者时，才与业务状态、审计和必要幂等记录同事务追加 |
| M5 查询、回答、反馈等没有上述冻结事件的写入 | 同上；按安全规则记录审计或调用记录 | 不发布业务事件 |
| M1 用户、角色、密码等安全状态变化 | 经过认证的交互 actor | 仅当本目录存在已冻结且登记实际消费者的安全事件时追加；不得为形式统一发布 |
| 登录成功后的会话签发、显式注销 | 完成认证的用户 | 不发布业务事件；按适用规则审计 |
| 被动会话活动续期 | 完成认证的用户 | 不发布业务事件，不逐次写业务审计；使用结构化日志和指标 |
| 登录失败、限流等认证子系统记账 | authentication 受管服务 actor | 不发布业务事件；按安全规则审计 |
| 首次 bootstrap | bootstrap 受管服务 actor，仅限生产激活前 | 不属于正常生产流量事件；使用独立 request ID 和审计 |
| Worker heartbeat/lease/retry | worker 受管服务 actor；有用户发起人时保留 initiator | 不发布业务事件，也不逐次写业务审计；使用日志/指标。明确登记的领域结果事件除外 |

调用方不得提交裸 `actorId`、`initiatorId` 或 reviewer。M2/M3/M5 接入生产事务前，必须使用 M1 冻结的 `AuthenticatedActor -> AuditEventInput` 强类型桥接和事件级审计 metadata 白名单；其当前实现状态见追踪矩阵。

没有实际消费者、幂等和回放语义的写操作不得为了“统一架构”发布 outbox。Mock、测试消费者、待建 M4 或表格中的预期消费者均不能满足生产发布条件。

## 4. 事件登记

下列事件均为提议。表中“预期消费者”只说明设计方向，不构成实际消费者登记，也不授权生产发布。

| 事件 | 生命周期 | 生产者 | 预期消费者 | 冻结前必须补齐 |
| --- | --- | --- | --- | --- |
| `DocumentParseRequested.v1` | 提议 | M2 documents | M4 worker | 文件引用白名单、解析配置版本、去重键、取消/失败语义、实际 consumer ID 和重放 |
| `KnowledgePublished.v1` | 提议 | M2 knowledge | M4 indexing/cache | 有效版本切换点、索引世代、实际 consumer ID、幂等与重放 |
| `KnowledgeRetired.v1` | 提议 | M2 knowledge | M4 indexing/cache | 退役版本、派生数据失效、实际 consumer ID、幂等与重放 |
| `RepairCasePublished.v1` | 提议 | M2 cases | M4 indexing/cache | 审核决定、有效修订、附件引用、实际 consumer ID、幂等与重放 |
| `RepairCaseRetired.v1` | 提议 | M2 cases | M4 indexing/cache | 废弃/替换语义、派生数据失效、实际 consumer ID、幂等与重放 |
| `WorkflowPublished.v1` | 提议 | M3 workflows | M4 indexing/cache | 有效版本、设备适用范围、实际 consumer ID、幂等与重放 |
| `WorkflowRetired.v1` | 提议 | M3 workflows | M4 indexing/cache | 退役版本、匹配缓存失效、实际 consumer ID、幂等与重放 |

每个“已冻结”事件必须在本表或链接的版本化 schema 记录以下稳定信息：

- 生产者模块、聚合和唯一事务触发点。
- 实际 consumer ID、所有模块、处理器公共端口和可部署责任边界。
- payload 字段、类型、可空性、敏感性、大小上限和正反例。
- producer dedup key、consumer idempotency key、同聚合顺序、重复/乱序处理。
- claim/lease、重试、dead-letter、恢复、重放和积压升级/回滚。
- actor/initiator、权限、审计、保留和隐私规则。
- major 兼容、双读/双写或消费者迁移窗口，以及生产者/消费者契约测试。

## 5. 变更流程

1. 修改前读取 `docs/change-log/INDEX.md`、本目录、生产者/消费者相关模块的最近记录和执行时 migration head。
2. 生产者提出事件版本、封闭 payload DTO、事务触发点和回滚语义；消费者提交实际 consumer ID、公共处理端口、幂等/重放和失败恢复规则。
3. M0 确认 append/envelope 与 ClaimPort 边界；M1 确认 actor/initiator 和审计输入；领域所有者确认权限与隐私。
4. 同一逻辑变更内更新本目录、版本化 schema/样例、生产者与消费者契约测试，并在 `docs/change-log/` 新增日志、更新 `INDEX.md`。
5. 不兼容字段变化新增 major 版本并保留迁移期消费者；禁止原地改变已冻结字段含义。
6. 废弃前确认所有消费者迁移、积压 outbox、重放工具、保留期和回滚方案。

## 6. 稳定接入顺序

1. M1 冻结类型化 actor 到审计输入的桥接、服务账户 readiness 和适用权限/审核容量端口。
2. 生产者与消费者共同提交事件 schema、consumer ID、事务触发点、幂等/回放设计和契约测试草案；此时事件仍为“提议”。
3. M0 冻结 ClaimPort 的 claim/lease/retry/replay 与并发语义。
4. M4 通过 ClaimPort 建立可定位的生产 handler、去重与失败恢复实现，完成生产者/消费者契约测试并登记为实际消费者。
5. payload、主体、权限、兼容和实际消费者全部满足冻结条件后，本目录才把事件从“提议”改为“已冻结”；这一变化不自动提升功能实现状态。
6. 消费链完成数据库、故障恢复和重放集成验证后，生产者才可在对应环境启用发布。
