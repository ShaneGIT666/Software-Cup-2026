# 官方赛题要求最终测试报告

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
