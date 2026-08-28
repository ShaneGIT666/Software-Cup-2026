# 收敛唯一设计来源并重排无冲突后续路线

- 变更标识：`2026-08-29-024-unified-design-source`
- 日期：`2026-08-29`
- 记录状态：`变更已结束`
- 状态对象：`仓库现行设计来源、M0～M7 稳定设计与仅含未完成工作的后续开发路线`
- 功能验证状态：`已设计`
- 所属模块：`M7`；协作模块：`M0、M1、M2、M3、M4、M5、M6`
- 需求追踪：`DATA-02、API-01、AUTH-11～AUTH-13、NFR-MNT-01～NFR-MNT-02、NFR-MNT-05～NFR-MNT-06`
- 关联记录：`2026-08-14-015-historical-document-baseline-boundary`、`2026-08-17-018-current-document-baseline-closure`、`2026-08-17-020-current-contract-document-correction`、`2026-08-17-021-document-source-and-event-enablement-closure`、`2026-08-28-022-follow-up-development-plan`、`2026-08-29-023-m0-p0-contract-closure`
- 规范来源影响：`需求语义（无语义变更，仅统一来源）、动态状态、领域事件、公共契约`

## 改动内容

- 逐份复核本地代码、SRS、现行追踪矩阵、全部 `docs/design/` 文档、部署/架构/项目历史材料和最近变更记录，将仍有效的架构、HTTP/数据/身份/审计/事件/部署及模块设计整合进 `follow-up-development-plan.md`。
- 将已完成的 M0 P0、D1/D1.1/D1.2 等阶段从后续任务中删除，只把需要长期维持的行为保留为稳定非回归契约；旧原型和比赛阶段计划不再进入现行路线。
- 明确此后仓库只有一个可持续修改的设计文件：事件、公共契约、部署和后续路线均在同一文件的固定锚点原位更新，不得新建模块设计、补充方案或阶段设计文件。
- 删除 `docs/design/` 下八份重复、被替代或历史草案及 `.gitkeep`；历史变更日志正文和其他已带历史警告的材料保持不变，旧路径只从 Git 历史追溯。
- 把剩余工作重排为公共扩展接缝与 M1 生产门面、PostgreSQL 16、设备同步事实源、M0/M4 异步基座、三个生产者/实际消费者纵向事件切片、M5、M6 和持续 M7。任何依赖异步一致性的生产入口都不能早于对应消费者与生产启用门禁。
- 消除后续冲突：全局 OpenAPI 门禁改为待实现的动态枚举，具体 operation 映射归所属模块；响应 helper 将要求具体模型；M0 拥有 ClaimPort PostgreSQL 适配器/迁移，M4 拥有 registry/Runner/消费者；权限未变更 schema 时不造迁移；遗留 `LoginThrottle` 禁止新引用且只能通过新 revision 条件清理。
- 经独立复核进一步拆清实体所有权：delivery/lease/operation ledger 与 `SystemSettingMetadata` 归 M0，索引任务/世代归 M4，`ProviderCallRecord` 归 M5；补回 `APP_ENV`、幂等键、readiness reason 和 13 个 M1 operation 的稳定精确契约，并把未版本化 append 测试事件名列入 R1 修正项。
- 将根 README、后端/前端/测试资产说明、SRS、现行追踪矩阵和日志规则全部切换到统一文件锚点，并纠正前端 DTO 现状、ClaimPort 冻结状态和 Claim 适配器所有权。

## 文件与数据影响

- `docs/design/follow-up-development-plan.md`：重写为唯一现行设计来源，新增稳定锚点、完整设计、R1～R8 未完成路线和冲突/验收门禁。
- `docs/design/{api-contract-draft,data-model-draft,event-catalog,m0-m1-deployment-readiness-plan,m0-public-contract,m1-identity-audit-design,module-build-progress-and-interface-plan,software-design-doc}.md`、`docs/design/.gitkeep`：删除；内容由统一方案吸收或判定为历史原型，不再并行维护。
- `README.md`、`backend/README.md`、`frontend/README.md`、`data/external-test/README.md`、`docs/requirements/{software-requirements-spec,current-traceability-matrix}.md`、`docs/change-log/README.md`：修改现行来源、锚点与冲突表述。
- `docs/change-log/2026-08-29-024-unified-design-source.md`、`docs/change-log/INDEX.md`：新增本记录并登记索引。
- 运行时代码、API 路径/DTO、数据库表、Alembic revision、配置项、领域事件生命周期和数据：无。事件仍保持统一方案登记的当前生命周期，不因文档合并自动启用。

## 依赖与冲突检查

- 已检查：提交 `4f67482` 当前代码、v1 路由/响应模型注册、数据库模型/迁移、readiness、M0/M1 公共端口、旧前后端原型、SRS、追踪矩阵、全部现有设计文件、历史架构/部署/项目/研究/提交方案和记录 015/018/020/021/022/023。
- 结论：设计内容只有一个写入点；SRS 只保留需求与稳定接入约束，追踪矩阵只保留动态状态。迁移单 head 串行、模块目录所有权、事件逐条纵向启用、Mock/旧表面冻结和公开端口依赖规则避免了后续并行重复实现及跨模块私表冲突。
- 状态与证据：本次只完成设计与文档治理，因此状态对象最高为“已设计”，不提升任何代码、PostgreSQL、Worker、浏览器、代理、部署或产品功能状态；记录 023 的既有单元证据也未被外推。

## 验证与回滚

- 验证：现行文档本地链接与锚点检查通过；统一方案显式锚点无重复。
- 验证：`docs/design/` 文件数为 `1`，唯一文件为 `follow-up-development-plan.md`；排除明确历史材料和历史日志后，现行 Markdown 对已删除设计文件的残留引用为 `0`。
- 验证：`git diff --check` 通过；本次未修改运行时代码，未重复执行后端、前端或 PostgreSQL 测试。
- 回滚：将本记录涉及的文档作为一个逻辑单元整体恢复到变更前版本，并从 Git 恢复被删除草案；不涉及数据库降级、数据恢复、API 兼容或事件补偿。部分恢复会重新产生两个设计来源，不允许作为有效回滚。

## 后续开发提示

- 所有后续设计变更只修改 `docs/design/follow-up-development-plan.md` 对应锚点；不得新建设计文件，也不得把已完成阶段重新放回后续路线。
- 下一代码工作包从统一方案 R1 开始：先关闭动态 OpenAPI/具体 response model、typed audit、受管服务主体、审核容量和权限门禁，再进入 PostgreSQL 16 与纵向领域切片。
