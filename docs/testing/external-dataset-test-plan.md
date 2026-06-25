# 外部维修资料与数据集测试计划

更新时间：2026-06-25

本文说明如何使用来源明确的外部资料验证系统的资料上传、解析、审核、检索、RAG 引用和评测能力。外部数据只用于测试与演示，不默认进入正式知识库。

## 1. 数据源选择

| 数据源 | 类型 | 许可证/来源 | 本项目用途 | 当前状态 |
| --- | --- | --- | --- | --- |
| SAPID `maintenance-manual.pdf` | PDF 样例 | GitHub `sreejitheg/SAPID`，Apache-2.0 | PDF 上传解析、`pending_review`、审核入库烟测；下载后必须通过 `%PDF` 校验 | P0 |
| UCI AI4I 2020 Predictive Maintenance Dataset | 表格预测性维护数据 | UCI，CC BY 4.0 | 生成中文维修案例和 30 条外部开发评测题 | P0 |
| NASA PCoE Data Repository | 发动机、轴承、电池等预测性维护数据 | NASA 官方数据仓库 | 后续扩展发动机退化、轴承、电池案例 | reference only |
| MIMII Dataset | 工业设备异常声音 | Zenodo，CC BY-SA 4.0 | 后续多模态/声音异常演示，小样本使用 | reference only |
| CWRU Bearing Data Center | 轴承振动数据 | Case Western Reserve University | 后续轴承故障诊断案例 | reference only |

不纳入正式测试包的资料：来源不明的厂商维修手册、论坛搬运 PDF、授权不清楚的汽车/设备 service manual。

## 2. 生成与准备

```powershell
.\backend\.venv\Scripts\python.exe scripts\prepare_external_test_data.py --dry-run --source all
.\backend\.venv\Scripts\python.exe scripts\prepare_external_test_data.py --source ai4i
.\backend\.venv\Scripts\python.exe scripts\prepare_external_test_data.py --source sapid --max-mb 8
```

脚本行为：

1. `--dry-run` 只输出将要生成或下载的文件，不写入磁盘。
2. `--source ai4i` 写入小样本 CSV 和中文案例 JSON。
3. `--source sapid` 下载小型 PDF 样例；下载失败或文件不是合法 PDF 只报告错误，不影响主系统运行。
4. `raw/`、`cache/`、`downloads/` 目录默认不提交。

## 3. 测试流程

1. PDF 解析烟测
   - 上传 `data/external-test/pdf/maintenance-manual-sapid.pdf`。
   - 预期解析结果和 chunks 默认进入 `pending_review`。
   - 审核通过一个 chunk 后，再验证 `/api/search` 可以命中该 approved chunk。

2. 外部案例审核
   - 查看 `data/external-test/cases/ai4i-generated-maintenance-cases.json`。
   - 外部生成案例默认 `review_status=pending_review`。
   - 审核通过前不得进入正式检索或 RAG 证据。

3. 外部评测
   - 使用 `data/evaluation/rag-eval-external-dev.json`。
   - 该评测集适合在 AI4I 外部案例导入并审核后运行。
   - 未导入或未审核时命中率低是预期结果，重点观察 forbidden source 和 approved-only 隔离。

示例命令：

```powershell
.\backend\.venv\Scripts\python.exe scripts\run_rag_eval.py --dataset data\evaluation\rag-eval-external-dev.json --mode keyword
```

## 4. 答辩口径

可以说明：

1. 系统可接入公开维修资料和预测性维护数据，不局限于内置样例。
2. 外部资料默认不会直接进入正式知识库，必须经过 `pending_review` 和人工审核。
3. 评测集与检索 runner 分离，便于比较后续检索增强前后的效果。
4. 真实大文件和版权不清晰资料不进入仓库，保证交付可复现且风险可控。

不要宣称：

1. AI4I 表格数据本身就是维修手册。
2. 未审核外部案例可以直接作为正式检修依据。
3. 来源不明 PDF 属于项目正式知识来源。
