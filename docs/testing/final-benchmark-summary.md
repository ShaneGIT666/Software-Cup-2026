# 最终跑分摘要

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
