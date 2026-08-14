# 最终工程测试报告

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行口径以[根 README](../../README.md)、[软件需求规格说明书](../requirements/software-requirements-spec.md)和[修改日志索引](../change-log/INDEX.md)为准；发生冲突时，以这些现行文件及相关模块最新记录为准。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

版本日期：2026-06-27

## 1. 本轮变更摘要

本轮是提交前最后一次前端产品化、初始化配置和文档同步收口，未修改后端核心业务逻辑，未新增依赖，未改变现有 API 协议。

完成内容：

- 前端信息架构优化：默认首页改为“检修助手”，管理审核功能迁移到“管理中心”，技术状态迁移到“系统状态”。
- 检修助手五步链路：描述故障、查看依据、生成指引、复核修正、提交经验。
- 知识关系图可视化增强：摘要统计、图例、轻量 SVG 网络图、节点详情、典型关系路径和 approved-only 说明。
- 初始化配置脚本：支持离线演示模式和真实 LLM 模式，API Key 脱敏显示，不进入 Git 和日志。
- 产品化细节增强：首次使用引导、一键演示样例、下一步提示、空状态、错误状态和术语说明。
- 文档同步：README、提交文档、演示 runbook、7 分钟脚本、截图清单、交付总结、合规矩阵、架构说明。

## 2. 前端构建结果

命令：

```powershell
cd frontend
npm.cmd run build
```

结果：通过。

本轮构建结果：

```text
✓ 3328 modules transformed.
✓ built in 4.61s
```

已知 warning：

- VueUse pure annotation warning。
- Vite chunk size warning。

以上 warning 不阻塞演示。

## 3. 脚本检查结果

本轮新增脚本：

- `scripts/init-config.ps1`
- `scripts/init-config.sh`
- `scripts/validate-provider.ps1`
- `scripts/validate-provider.sh`

计划检查命令：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\init-config.ps1 -Help
powershell -ExecutionPolicy Bypass -File .\scripts\validate-provider.ps1 -Help
bash -n scripts/init-config.sh
bash -n scripts/validate-provider.sh
```

最终提交前以实际命令输出为准。

## 4. 后端测试基线

上一轮后端全量测试：

```text
174 passed in 729.77s
```

本轮未改后端核心逻辑和 API 协议，因此不强制重新执行后端全量测试。若时间允许，可在提交后再次运行：

```powershell
.\backend\.venv\Scripts\python.exe -m pytest tests\ -q
```

## 5. API 冒烟基线

上一轮已完成临时目录隔离冒烟，覆盖：

- `GET /api/health`
- `GET /api/providers/status`
- `POST /api/search`
- `POST /api/rag/answer`
- `POST /api/multimodal/diagnosis`
- `POST /api/rag/feedback`
- `PATCH /api/rag/feedback/{id}/review`
- `GET /api/knowledge/graph`

## 6. LoongArch / Kylin 结果

已有目标环境复验记录显示主链路可迁移运行。最终提交前建议再次执行：

```bash
bash scripts/loongarch-final-verify.sh
```

如需要 Docker 路径：

```bash
bash scripts/loongarch-final-verify.sh --docker
```

## 7. 敏感文件检查原则

不得提交：

- `.env`
- API Key
- `.venv`
- `node_modules`
- `frontend/dist`
- `data/uploads`
- `data/knowledge`
- 日志、截图、视频、压缩包和运行缓存

本轮脚本只写本地 `.env`，并确保 `.gitignore` 忽略 `.env`。

## 8. 是否建议用于最终演示视频

建议。新版界面更适合录制：默认首页是检修助手，主流程清晰；管理中心和系统状态可按答辩需要切换展示；知识关系图具备摘要、图例、SVG 可视化和节点详情，能够直观说明知识沉淀。

## P0 补充：官方 PDF 视觉资产阻断修复

本轮修复官方“摩托车发动机维修手册”上传后图片资产计数为 0 的演示阻断问题。根因是 MinerU 超时后 PDF 会 fallback 到 pypdf 文本解析，但后续图片资产分析只读取 MinerU 输出 assets；当 assets 为空时文档被标记为 `skipped/no_assets`，不会生成可审核的图示页片段。

修复后：当 PDF 的 MinerU assets 缺失时，系统自动生成 `pdf_page_visual_asset` 页面视觉资产 fallback 片段。官方 PDF 手动验证生成 12 个页面视觉资产片段，`assetAnalysisStatus=fallback_completed`，`assetAnalysisFallbackCount=1`，文本 chunk 仍正常保留。
