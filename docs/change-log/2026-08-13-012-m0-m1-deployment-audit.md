# 复核 M0/M1 部署并冻结后续无冲突接入方案

- 变更标识：`2026-08-13-012-m0-m1-deployment-audit`
- 日期：`2026-08-13`
- 记录状态：`变更已结束`
- 功能验证状态：`部署方案已设计；M0/M1 真实 PostgreSQL、Windows Service 与系统验收未完成`
- 所属模块：`M7`；协作模块：`M0`、`M1`、`M2`～`M6`
- 需求追踪：`AUTH-01`～`AUTH-12`、`FR-IAM-01`～`FR-IAM-05`、`FR-OPS-01`～`FR-OPS-04`、`DATA-01`～`DATA-08`、`API-01`～`API-07`、`NFR-PORT`、`NFR-REL`、`NFR-SEC`、`NFR-OBS`
- 关联记录：`2026-08-13-010-module-progress-audit`、`2026-08-13-011-m1-local-identity-http`

## 改动内容

- 只读检查 M0/M1 路由、模型发现、事务、幂等、身份/审计端口、迁移、配置、启动/验证脚本、前端构建、部署目录和 SRS/设计边界。
- 实测本地后端回归、前端生产构建、离线迁移、真实 Uvicorn 进程、当前/生产 readiness 和 M1 失败关闭行为。
- 识别生产数据库可被错误降为可选、M0 readiness 直接依赖 M1、旧 API/静态目录绕过认证、产品配置/Windows Service 工件缺失、outbox 公共端口缺失和迁移并行冲突等问题。
- 新增 M0/M1 部署与接入设计，冻结后续模块可消费的公共端口、readiness contributor、旧表面隔离、Windows/Linux 包装边界、测试矩阵、集成顺序与并行条件。
- 未修改 M0/M1 业务代码、数据库迁移、API、DTO、SRS 功能状态或运行数据；没有把设计项标记为已实现。

## 文件与数据影响

- `docs/design/m0-m1-deployment-readiness-plan.md`；新增：部署现状、冲突、目标拓扑、接口、工件、验收和并行方案。
- `docs/design/module-build-progress-and-interface-plan.md`；修改：引用第 012 号部署方案，明确其尚未实施。
- `docs/change-log/INDEX.md`、本记录；新增/修改：登记本轮复核。
- `frontend/dist/`；由验证命令重新生成的可重建忽略工件，不是 M6 登录接入完成证据。
- 代码、API、DTO、数据库 schema/数据、配置密钥和运行服务：无修改；烟测 Uvicorn 已停止。

## 依赖与冲突检查

- 已检查：日志 001～011、SRS 第 1/10/12/14 节、M0/M1 设计、`main.py`、v1/ORM 注册表、迁移 `0001`～`0004`、`.env`/`.env.example`、后端/前端依赖、Windows/容器/验证脚本和部署目录。
- 结论：M0 的路由/模型发现和 M1 领域所有权可保留；后续模块通过冻结端口和预留文件开发，无需修改 M1 私有实现。必须先由 M0/M7 关闭 readiness、旧表面、outbox 和 PostgreSQL 验收门槛；正式 migration revision 串行集成，以避免 M2/M3 多头。

## 验证与回滚

- 后端：`backend/.venv/Scripts/python.exe -m pytest -q` → `239 passed, 25 skipped`；M1 PostgreSQL 3 项未执行。
- 前端：`npm.cmd run build` 成功；产生约 1.05 MB 单块警告。
- 环境：虚拟环境 Python 3.12.7、`pip check` 通过；本机未发现 PostgreSQL/psql、Docker 或 CI 配置，目标 Python 3.11 基线未复验。
- 迁移：单一 head `20260813_0004`；离线 upgrade SQL 成功；无在线数据库操作。
- 真实进程：live=200、当前可选模式 ready=200、前端首页=200、M1 登录=503；生产必需依赖缺失时 ready=503。另证实生产数据库配置为可选且只配置认证密钥时 ready 会误报 200，已记录为 P0 设计缺口。
- 旧 readiness：7 项离线 mock 检查通过，仅作为历史原型证据。
- 回滚：删除新增设计/日志并恢复进度文档和索引即可；代码、数据库和配置不需要回滚。`frontend/dist` 可由后续构建覆盖或清理。

## 后续开发提示

- 下一批先实施方案第 11 节的 M0.1 公共端口，不直接开始 M2/M3 真实身份接入。
- 在真实 PostgreSQL、旧入口隔离和 Windows Service 验收前，M0/M1 继续标记为“代码已搭建/进程内已验证，部署未完成”。
- M2/M3/M6 可使用契约 Mock 并行；不得导入 M1 ORM/Repository、修改 M0 root router/模型注册表或并行占用同一迁移后继编号。

