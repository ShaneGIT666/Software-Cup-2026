# 脚本适用范围索引

> 本文件只维护脚本的稳定用途分类和证据边界，不维护动态测试数量或完成状态。产品范围以 [SRS](../docs/requirements/software-requirements-spec.md) 为准，当前状态以 [现行需求追踪矩阵](../docs/requirements/current-traceability-matrix.md) 为准，执行证据只进入 [修改日志](../docs/change-log/INDEX.md)。

`scripts/` 当前不包含可验收的生产安装器、Windows Service 工件或 Linux 发行包。脚本名中的 `production`、`readiness`、`final`、`deploy` 或 `docker` 是历史命名，不能单独构成生产就绪、最终验收或部署完成证据。

## 1. Windows 开发辅助

| 脚本 | 用途与边界 |
| --- | --- |
| `dev.ps1`（通常由根目录 `dev.bat` 调用） | 当前 Windows 原型的启动、停止、状态、日志和可达性检查入口。`verify` 只检查旧 `/api/health` 和前端页面，不检查生产 readiness。 |
| `start-backend.ps1` | 开发 Uvicorn 入口，使用 `--reload`；虚拟环境缺失时会调用含特定机器路径的 `setup-anaconda.ps1`。不得作为 Windows Service 或可移植安装入口。 |
| `start-frontend.ps1` | Vite 开发服务入口。`node_modules` 缺失时会执行 `npm install`，因此只是本地便利脚本，不是锁定安装或 CI 证据。 |
| `start-dev.ps1` / `stop-dev.ps1` | 另一组历史兼容开发启停入口。新的本地说明统一引用 `dev.bat`，不应为这组脚本另建一套产品运行契约。 |
| `build-frontend.ps1` | 使用现有 `node_modules` 执行类型检查和 Vite 构建。它不安装依赖，也不证明浏览器 E2E 通过。 |
| `run-backend-tests.ps1` | 运行当前 pytest 集。虚拟环境缺失时具有与 `start-backend.ps1` 相同的本机 Anaconda 假设；skip 和真实依赖缺失必须单独记录。 |
| `setup-anaconda.ps1` | 只为特定历史开发机保留的环境辅助，包含固定用户路径假设。不得作为团队统一安装或 Windows 交付入口。 |

## 2. 条件性验证与评测

| 脚本 | 前置条件与证据边界 |
| --- | --- |
| `run-local-verification.ps1` | 组合后端 pytest、前端构建和旧 JSON/mock 原型闭环。脚本显示名已改为“Legacy prototype offline smoke”；下游文件名中的 `production-readiness` 仍是历史命名。该链路不调用 `/api/v1/health/ready`，不得用于生产验收。 |
| `run-frontend-smoke.ps1` | 调用 `npm run test:e2e`。当前 `@playwright/test` 未写入 `package.json`/lockfile，因此此脚本尚不是可复现门禁。 |
| `prepare_external_test_data.py` | 准备外部评测数据；必须遵守数据授权、来源和提交策略，它不表示外部数据测试已完成。 |
| `evaluate_manual_recall.py` / `evaluate-manual-recall.ps1` | 特定手册数据集的召回评测工具。结果只适用于记录的数据集、配置和代码基线。 |
| `run_rag_eval.py` | RAG 评测报告辅助。不得用旧原型报告提升 M5 目标模块状态。 |
| `validate-provider.ps1` / `validate-provider.sh` | 查看旧 `/api/providers/status` 原型状态。不代替目标 Provider readiness、故障注入或生产降级验收。 |
| `run-json-store-maintenance.ps1` / `json_store_maintenance.py` | 只维护迁移期 JSON 原型存储；PostgreSQL 目标领域数据不得依赖它。 |

## 3. 迁移期或历史原型脚本

| 脚本 | 历史边界 |
| --- | --- |
| `init-config.ps1` / `init-config.sh` | 只生成旧原型 Provider/mock 配置，会在确认后覆盖根 `.env`；它们不生成 PostgreSQL、M1 身份、幂等密钥或生产存储配置。两个脚本现已在 help/输出中明示该边界；PowerShell 只指向 Windows 旧原型开发入口，shell 不声称存在受支持的 Linux 产品启动入口。 |
| `configure-api.ps1` | 旧 Provider API 交互配置工具，面向旧 `/api` 路由。不得作为目标生产密钥注入或预检工具。 |
| `production_readiness_check.py` / `run-production-readiness-check.ps1` | 强制使用临时目录和 mock Provider 运行旧 `/api` `TestClient` 闭环。无论通过与否，都不是 M0/M1 生产 readiness、真实 PostgreSQL 或部署证据。 |
| `Dockerfile` 的相关调用：`docker-build.ps1`、`docker-run.ps1`、`deploy-docker-vm.ps1` | 重现历史 LoongArch/竞赛原型容器。现有镜像同时设置 `APP_ENV=production`、mock Provider 和旧入口禁用，却没有目标 PostgreSQL、身份密钥、HTTPS Origin、v1 前端和所有必需 contributor，不能形成当前产品闭环。 |
| `loongarch-final-verify.sh` | 历史 LoongArch/麒麟原型验证，允许 mock、skip 和旧 `/api` 写入；不是 Windows 默认交付或 Ubuntu CI 证据。 |
| `run-final-benchmark.py` | 历史原型报告生成器。名称中的 `final` 不表示当前 SRS 性能、安全或发布门槛已通过。 |
| `package-demo.ps1` | 演示包辅助，不是带有 Service、迁移、备份恢复和升级回滚的产品交付包。 |

## 4. 生产与 CI 目标工件

产品级运维脚本只能放入 `deploy/` 的目标平台目录，不得通过重命名或包装上述原型脚本冒充。当前：

- `deploy/windows/` 尚不存在，无 preflight、Service、迁移、provisioning、备份恢复、升级回滚或卸载工件。
- `.github/` 尚不存在，无 Windows/Ubuntu/PostgreSQL 16 CI。
- `deploy/linux/` 尚不存在；Linux 生产发行包是可选交付物，Ubuntu CI 则是目标版本必须门槛。

后续建立生产工件时，Windows 默认参考代理为 Caddy；只有实际选用并完成同等安全与代理链验收后，IIS 才进入对应交付范围。安装期还必须实现 SRS 第 10.1 节规定的受限 provisioning 阶段，不得在实例未激活且 `/api/v1/health/ready` 未成功时报告部署完成。

## 5. 可复现执行规则

- 有 `package-lock.json` 时，常规安装和 CI 使用 `npm ci`；只有明确修改依赖时使用 `npm install` 并同步提交 manifest/lockfile。
- 当前 Playwright 依赖未锁定，不得依赖 `npx` 临时下载的版本生成交付证据。
- Python 生产依赖和容器基础镜像尚未完成全量锁定；宽版本范围、本机已安装包或一次成功构建不能代替锁定依赖证据。
- 任何脚本执行结果必须记录代码基线、环境、命令、结果、skip 和未关闭问题；只能支持它实际覆盖的实现状态。
