# 阶段 0 现行契约与状态口径统一

- 变更标识：`2026-08-17-016-stage0-contract-alignment`
- 日期：`2026-08-17`
- 记录状态：`变更已结束`（只描述本次修改记录，不表示需求功能完成）
- 功能验证状态：`已设计`
- 所属模块：`M7`；协作模块：`M0、M1、M2、M3、M4、M6`
- 需求追踪：`AUTH-01～AUTH-12、DATA-02～DATA-08、API-01～API-07、FR-OPS-01、NFR-REL-06、NFR-PORT-01～05`
- 关联记录：`2026-08-14-013-m0-m1-public-integration-gates`、`2026-08-14-014-readme-baseline-alignment`、`2026-08-14-015-historical-document-baseline-boundary`

## 改动内容

- 将实现进度统一为“未开始/已设计/代码已搭建/单元已验证/集成已验证/已完成”六级状态，将“原型代码存在/待改造/可选”分别限定为资产、优先级和范围标记。
- 明确进程内 `TestClient`、Mock 和离线 SQL 不属于“集成已验证”，并收紧验证记录字段。
- 将 readiness 规范路径统一为 `/api/v1/health/ready`，冻结八类 contributor 预留位置和 `ReadinessDetails` 脱敏白名单契约。
- 冻结 `APP_ENV` 三值失败关闭、CORS 暴露 `ETag`、未捕获 v1 异常使用 `INTERNAL_ERROR/500` 脱敏信封的 M0 目标契约。
- 用写操作分类矩阵统一 outbox 边界：已登记消费者的关键 M2/M3 领域变更必须发布；认证维护、当前 bootstrap 和 Worker 租约维护不发布业务 outbox。
- 将 M1 需求范围补齐到 AUTH-12、DATA-08 和 API-07 的相关条款，同时记录 bootstrap 当前 actor/request ID 与目标审计契约的未关闭差距。
- 将 `docs/deployment/` 明确归类为历史资料，并修正从仓库根目录执行 bootstrap 的包路径说明。

## 文件与数据影响

- `README.md`、`backend/README.md`；修改。
- `docs/requirements/software-requirements-spec.md`；修改。
- `docs/design/m0-public-contract.md`、`m1-identity-audit-design.md`、`module-build-progress-and-interface-plan.md`、`m0-m1-deployment-readiness-plan.md`；修改。
- `docs/change-log/TEMPLATE.md`；修改功能验证状态枚举。
- 数据库、迁移、运行时 API/DTO/事件和配置值：无实现变更；本记录只冻结阶段 1 及后续模块的现行契约。

## 依赖与冲突检查

- 已检查：`docs/change-log/INDEX.md`、模板、记录 013～015、SRS、M0 公共契约、M1 设计、模块进度计划、M0/M1 部署就绪计划、根/后端 README、当前代码和测试，以及 migration head `20260814_0005`。
- 结论：现行文档的状态、readiness、outbox、M1 追踪和历史目录边界已统一。阶段 1 尚需实现 M0 配置/异常/CORS/readiness 契约；M1 bootstrap 审计主体修正不属于本阶段代码范围。

## 验证与回滚

- 验证：使用 `rg` 对状态枚举、`/api/v1/health/ready`、`/health/ready`、outbox、`ReadinessProbe`、M1 需求范围和 bootstrap 命令进行交叉检索；仓库根目录的 `backend.app...bootstrap --help` 和 `backend/` 目录的 `app...bootstrap --help` 均返回退出码 0。阶段 1 完成后已与第 017 号记录的代码测试和文档链接检查一并复核。
- 回滚：按本记录“文件与数据影响”逐文件恢复文档片段；无数据迁移或运行数据回滚。

## 后续开发提示

- 阶段 1 必须使用本记录冻结的 `INTERNAL_ERROR`、`APP_ENV`、CORS 和 `ReadinessDetails` 契约，并增加缺陷回归测试。
- 后续 M1 变更前先解决 bootstrap 受控系统主体与独立操作标识；在没有冻结事件消费者前不得为 M1 写操作泛化发布 outbox。
