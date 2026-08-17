# 现行领域事件目录

> 版本：1.0-draft<br>
> 更新日期：2026-08-17<br>
> 主责：M0 契约治理；事件生产者与 M4 消费者共同评审

## 1. 作用与唯一来源

本文件是目标产品版本化领域事件、生产者、消费者和 outbox 适用范围的唯一现行目录。SRS 只定义“何时必须可靠发布事件”的需求语义，M0 公共契约只定义 outbox 写端口；具体事件的增加、冻结、升级和废弃只在本文件及对应代码/测试/修改日志记录，避免重复修改 README、SRS 和多个设计文档。

事件目录生命周期使用“提议”“已冻结”“已废弃”，仅描述事件契约，不是功能实现状态。功能状态仍只使用“未开始”“已设计”“代码已搭建”“单元已验证”“集成已验证”“已完成”。

## 2. 公共信封

已冻结事件必须使用 M0 `OutboxEventInput`，至少包含：

| 字段 | 规则 |
| --- | --- |
| `eventId` | outbox 写端生成的稳定唯一 ID |
| `eventType` | `<Domain><Fact>.v<major>`；major 改变表示不兼容升级 |
| `aggregateType` | 稳定领域聚合类型 |
| `aggregateId` | 稳定聚合 ID，不使用路径或显示名 |
| `versionId` | 产生事件的业务版本；不得使用伪造的当前时间代替 |
| `requestId` | 原始请求或受控任务的 request ID |
| `occurredAt` | UTC、有时区时间 |
| `payload` | 事件级白名单 DTO；禁止密钥、令牌、Cookie、密码、连接串、绝对路径和任意请求体 |

生产者在拥有领域事务的 Session 中调用 `OutboxWriter.append()`；Writer 不 commit/rollback，不返回 ORM。消费者通过尚待 M0 冻结的 `OutboxClaimPort` 领取，不能直接导入或更新 `db.models.OutboxEvent`。

## 3. 操作分类

| 操作类型 | 已认证主体 | outbox |
| --- | --- | --- |
| M2/M3/M5 可对外观察且已登记消费者的领域事实变化 | `CurrentUser`；异步延续使用受管服务用户并保留发起身份 | 必须在业务状态、审计和必要幂等记录的同一事务追加 |
| M5 查询、回答或反馈等当前未登记消费者的写入 | `CurrentUser`；异步延续使用受管服务用户并保留发起身份 | 当前不发布业务事件 |
| M1 用户/角色/密码等安全状态变化 | `CurrentUser` | 仅在本目录已有冻结消费者时追加；当前没有 |
| 登录成功后的会话签发/续期/注销 | 完成认证的用户 | 不发布业务事件 |
| 登录失败、限流等认证子系统记账 | 固定认证受管服务用户 | 不发布业务事件；主体代码已单元验证，真实 PostgreSQL 待 D2 |
| 首次 bootstrap | 固定 bootstrap 受管服务用户，仅限生产激活前 | 不属于生产运行事件；独立请求标识和实例生命周期已单元验证，真实 PostgreSQL 待 D2 |
| Worker heartbeat/lease/retry | 受管服务用户 | 不发布业务事件；已登记的显式领域结果事件除外 |

没有在本目录登记消费者的写操作不得为了形式统一发布 outbox。仅有生产者设想而没有明确消费者、幂等和回放语义的事件只能保持“提议”。

## 4. 当前事件清单

截至 2026-08-17，仓库只有 M0 outbox 公共写端口和表结构，尚无目标领域生产者或 M4 目标消费者，因此没有“已冻结并已实现”的领域事件。

| 事件 | 生命周期 | 生产者 | 预期消费者 | 当前边界 |
| --- | --- | --- | --- | --- |
| `DocumentParseRequested.v1` | 提议 | M2 documents | M4 worker | 待冻结任务输入白名单、文件引用、去重键、失败/取消语义 |
| `KnowledgePublished.v1` | 提议 | M2 knowledge | M4 indexing/cache | 待冻结有效版本切换、索引世代和重放语义 |
| `KnowledgeRetired.v1` | 提议 | M2 knowledge | M4 indexing/cache | 待冻结退役版本、派生数据失效和重放语义 |
| `RepairCasePublished.v1` | 提议 | M2 knowledge/cases | M4 indexing/cache | 待冻结案例审核决定、有效修订、附件引用和重放语义 |
| `RepairCaseRetired.v1` | 提议 | M2 knowledge/cases | M4 indexing/cache | 待冻结案例废弃/替换、派生数据失效和重放语义 |
| `WorkflowPublished.v1` | 提议 | M3 workflows | M4 indexing/cache | 待冻结有效版本、设备适用范围和重放语义 |
| `WorkflowRetired.v1` | 提议 | M3 workflows | M4 indexing/cache | 待冻结退役版本、匹配缓存失效和重放语义 |

提议名称用于设计和 Mock，不授权生产代码发布。只有生产者、消费者、payload schema、幂等键、顺序/重复处理、权限/隐私、失败恢复和契约测试均记录后，才能改为“已冻结”。

## 5. 变更流程

1. 修改前读取 `docs/change-log/INDEX.md`、本目录、生产者/消费者最新日志和 migration head。
2. 生产者提出事件版本、payload 白名单、事务触发点和回滚语义；M4 明确消费者、幂等与重放规则。
3. 同一逻辑变更内更新本目录、生产者/消费者契约测试、样例和修改日志。
4. 新增具体事件通常不修改 SRS、README 或 M0 公共契约；只有需求语义、公共信封或 outbox 端口变化时才修改这些文件。
5. 不兼容字段变化新增 major 版本并保留迁移期消费者；禁止原地改变已冻结字段含义。
6. 废弃事件前确认所有消费者、积压 outbox、重放工具和回滚方案已经处理。

## 6. 后续冻结顺序

1. D1.2 AUTH-13 主体和 OpenAPI 公共错误契约已完成单元验证；
2. D2 完成 PostgreSQL/M1 在线验收；
3. M2/M3 在各自领域事务设计中冻结实际事件；
4. M0 冻结 `OutboxClaimPort`；
5. M4 才接入真实消费者。
