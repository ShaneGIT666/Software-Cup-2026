# 官方赛题要求最终测试报告

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行口径以[根 README](../../README.md)、[软件需求规格说明书](../requirements/software-requirements-spec.md)和[修改日志索引](../change-log/INDEX.md)为准；发生冲突时，以这些现行文件及相关模块最新记录为准。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

日期：2026-06-26

## 范围

本报告覆盖官方要求中的主功能链路：资料上传解析、pending_review 审核隔离、检索、RAG 引用、标准化作业指引、故障图片诊断、案例经验沉淀、知识关系网络、Provider 状态与 fallback。

## 新增测试

| 测试文件 | 覆盖内容 |
|---|---|
| `tests/test_multimodal_diagnosis.py` | 故障图片 OCR/视觉线索进入诊断上下文，失败时降级 |
| `tests/test_maintenance_workflow_guidance.py` | 检修等级、作业前准备、风险控制、合规校验 |
| `tests/test_case_experience_review_flow.py` | 案例/经验总结 pending_review、审核通过可检索、拒绝不可检索 |
| `tests/test_chunk_revision_audit.py` | 人工修正生成 revision、审计事件、索引同步 |
| `tests/test_knowledge_graph_approved_only.py` | 知识关系网络只纳入 approved 对象 |
| `tests/test_official_compliance_smoke.py` | health、provider、search、RAG、case、review、graph 主链路烟测 |

## 本地通过命令

```powershell
.\backend\.venv\Scripts\python.exe -m pytest tests\ -q
cd frontend
npm.cmd run build
cd ..
powershell -ExecutionPolicy Bypass -File scripts\run-production-readiness-check.ps1
powershell -ExecutionPolicy Bypass -File scripts\run-json-store-maintenance.ps1
git diff --check
```

## 目标环境待补

请在 LoongArch/银河麒麟 VM 执行 `scripts/loongarch-final-verify.sh`，并把结果填入 `docs/testing/loongarch-final-verification-template.md`。
