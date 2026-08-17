# 最终跑分摘要

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行口径以[根 README](../../README.md)、[软件需求规格说明书](../requirements/software-requirements-spec.md)和[修改日志索引](../change-log/INDEX.md)为准；发生冲突时，以这些现行文件及相关模块最新记录为准。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

## 摘要

本项目最终跑分以“可运行主链路 + 可解释降级 + 可复验报告”为核心。所有数据应来自脚本或接口输出，不手写伪造数值。

## 记录方式

运行：

```bash
python scripts/run-final-benchmark.py
```

输出：

- `docs/testing/final-benchmark-results.json`
- 终端摘要

## 当前重点

- RAG 主链路是否可返回结构化回答。
- pending_review 是否隔离。
- 图片诊断是否可用或可降级。
- LoongArch/Kylin 环境是否可通过基础冒烟。
