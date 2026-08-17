# 外部测试资料

> 本文件只说明测试资产。产品需求、生产入库和当前实现状态分别以 [SRS](../../docs/requirements/software-requirements-spec.md)、[事件目录](../../docs/design/event-catalog.md)和[现行需求追踪矩阵](../../docs/requirements/current-traceability-matrix.md)为准。

本目录用于保存比赛演示和回归测试所需的外部资料清单、小样本数据和生成案例。这里的资料只用于验证上传解析、`pending_review` 隔离、审核入库、检索/RAG 引用和评测 runner，不作为默认正式知识库的一部分。

## 目录约定

- `manifest.json`：外部资料来源、许可证、用途和提交策略。
- `pdf/`：小型公开 PDF 样例，用于上传解析烟测。
- `tabular/`：可提交的小样本 CSV。
- `cases/`：由公开数据转写的中文维修案例，默认 `review_status=pending_review`。
- `raw/`、`cache/`、`downloads/`：下载缓存或大文件目录，默认被 `.gitignore` 忽略。

## 当前 P0 数据源

1. SAPID `maintenance-manual.pdf`
   - 来源：https://github.com/sreejitheg/SAPID
   - 许可证：Apache-2.0
   - 用途：PDF 上传、解析、审核链路烟测。
   - 注意：脚本会校验文件头必须为 `%PDF`；如果上游返回占位文本，不会提交到仓库。

2. UCI AI4I 2020 Predictive Maintenance Dataset
   - 来源：https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset
   - 许可证：CC BY 4.0
   - 用途：生成中文检修案例和外部评测问题。

## 使用方式

```powershell
.\backend\.venv\Scripts\python.exe scripts\prepare_external_test_data.py --dry-run --source all
.\backend\.venv\Scripts\python.exe scripts\prepare_external_test_data.py --source ai4i
.\backend\.venv\Scripts\python.exe scripts\prepare_external_test_data.py --source sapid --max-mb 8
```

下载失败不会影响主系统运行。外部生成案例只允许进入旧原型回归、隔离评测或测试数据库；即使在旧原型中经过审核，也不能据此成为目标生产事实。目标生产入库必须等待 M2 PostgreSQL 文档/知识版本、权限、受控文件和审核链路完成，并按现行追踪矩阵验收。
