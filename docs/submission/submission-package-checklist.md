# 提交包清单

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行文档的适用范围和来源优先级只以[根 README](../../README.md)第 1 节为入口；需求语义、动态状态、公共契约、领域事件和变更证据分别遵循该节指向的唯一事实源。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

版本日期：2026-06-27

## 必交材料

- [ ] `docs/submission/01-软件功能需求分析文档.md`
- [ ] `docs/submission/02-软件功能设计文档.md`
- [ ] `docs/submission/03-软件产品说明书.md`
- [ ] `docs/submission/04-软件功能测试报告.md`
- [ ] `docs/submission/05-软件安装包及部署文档.md`
- [ ] 软件源文件
- [ ] 软件功能演示 PPT
- [ ] 功能演示视频，mp4/avi/wmv，时长不超过 7 分钟
- [ ] 安装部署包
- [ ] `README.md`
- [ ] `.env.example`
- [ ] `scripts/loongarch-final-verify.sh`

## 建议附加材料

- [ ] `docs/product/final-checklist.md`
- [ ] `docs/project-management/final-engineering-test-report.md`
- [ ] `docs/testing/llm-provider-final-validation.md`
- [ ] `docs/testing/loongarch-final-verification.md`
- [ ] `docs/ppt-assets/final-demo-script-7min.md`
- [ ] `docs/ppt-assets/screenshot-checklist-final.md`
- [ ] `docs/ppt-assets/key-talking-points.md`
- [ ] `docs/ppt-assets/claim-boundary-table-final.md`

## 不得进入源码仓库

- [ ] `.env`
- [ ] API Key
- [ ] `.venv`
- [ ] `node_modules`
- [ ] `frontend/dist`，除非作为单独安装包产物，不进入源码仓库
- [ ] `data/uploads` 运行数据
- [ ] `data/knowledge` 运行数据
- [ ] 官方 PDF 或来源不明维修手册
- [ ] 临时日志
- [ ] 截图临时文件
- [ ] 视频临时文件
- [ ] zip/rar/7z 临时包

## 打包前复核

- [ ] 后端测试通过
- [ ] 前端构建通过
- [ ] readiness 通过
- [ ] JSON 巡检通过
- [ ] API 冒烟通过
- [ ] `git diff --check` 通过
- [ ] 敏感文件扫描通过
- [ ] 工作树干净或仅包含明确待提交文件
