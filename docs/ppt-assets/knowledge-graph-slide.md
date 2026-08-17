# PPT 素材：知识关系网络页

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行口径以[根 README](../../README.md)、[软件需求规格说明书](../requirements/software-requirements-spec.md)和[修改日志索引](../change-log/INDEX.md)为准；发生冲突时，以这些现行文件及相关模块最新记录为准。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

## 范围

轻量关系网络，不引入 Neo4j 等重依赖。

## 节点

- device
- component
- fault
- chunk
- case
- document
- review

## 关系

- device -> component
- device -> fault
- fault -> chunk
- fault -> case
- chunk -> document
- case -> review

## 约束

默认 approved-only，pending_review、rejected、deprecated、replaced 不进入正式图谱。
