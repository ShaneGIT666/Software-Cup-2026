# LoongArch 向量数据库路线

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行文档的适用范围和来源优先级只以[根 README](../../README.md)第 1 节为入口；需求语义、动态状态、公共契约、领域事件和变更证据分别遵循该节指向的唯一事实源。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

## 当前结论

比赛主链路采用 SQLite vector store。原因是它只依赖 Python 标准库 `sqlite3`，已在 LoongArch/银河麒麟 Docker 环境完成冒烟验证，可以满足两天内“可部署、可演示、可答辩”的硬约束。

## Chroma 不适合作为目标环境主依赖

调研与实测结论：

- Chroma 依赖原生 HNSW 组件，LoongArch wheel 不稳定。
- 现场 Docker 构建会卡在原生依赖安装，破坏交付确定性。
- 即使通过源码编译，也会引入 C/C++ 工具链、CPU 指令和镜像体积风险。
- 因此 Chroma 只保留为 `RAG_VECTOR_STORE=chroma` 或 `RAG_VECTOR_ENHANCER=chroma` 的兼容路径。

## sqlite-vec 路线

优点：

- 嵌入式部署，符合单机比赛环境。
- 查询能力优于 Python scan。
- 与 SQLite 主方案迁移成本低。

约束：

- 需要在 LoongArch 编译或获得可用扩展。
- 当前代码已提供 `RAG_VECTOR_SQLITE_ENGINE=sqlite_vec` 与 `SQLITE_VEC_EXTENSION_PATH`。
- 扩展不可用时自动回退 `python_scan`。

## Qdrant 路线

优点：

- 成熟开源向量数据库。
- API 清晰，适合后续服务化扩展。
- 当前代码提供 `RAG_VECTOR_ENHANCER=qdrant` 查询入口，并在返回前通过本地 SQLite 校验 approved chunk。

约束：

- 需要验证 LoongArch Docker 镜像或 Rust 源码构建。
- 比赛现场不把它作为硬依赖。
- Qdrant 查询失败时回退本地 SQLite，避免系统中断。

## 推荐演进

1. 当前比赛：SQLite Python scan 主链路。
2. 赛后优化：LoongArch 编译 sqlite-vec，并以环境变量灰度打开。
3. 数据量扩大后：引入 Qdrant 或 pgvector，配合运维监控与备份。
4. 企业落地：把审核、revision、权限和索引同步事件纳入数据库事务与审计。

