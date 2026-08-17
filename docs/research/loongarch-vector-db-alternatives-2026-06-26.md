# LoongArch Vector Store Alternatives, 2026-06-26

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行文档的适用范围和来源优先级只以[根 README](../../README.md)第 1 节为入口；需求语义、动态状态、公共契约、领域事件和变更证据分别遵循该节指向的唯一事实源。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

## Purpose

Chroma cannot remain the competition main-route vector database because `chromadb` / `chroma-hnswlib` failed installation on the LoongArch/Kylin VM. This note reviews mature alternatives using primary sources and applies the project rule: a dependency is not part of the delivery route until it runs on the target environment.

## Current Delivery Decision

Keep the built-in SQLite vector index as the default delivery vector store:

```env
RAG_VECTOR_STORE=sqlite
APP_VECTOR_DB_PATH=/app/runtime/knowledge/vector-index.sqlite3
RAG_EMBEDDING_PROVIDER=hash
```

Reasons:

- Uses Python stdlib `sqlite3`; no external vector database service or Python native wheel is required.
- Already integrated with the existing approved-only knowledge chunk state machine.
- Does not require native wheels, Docker sidecars, PostgreSQL extensions, Rust builds, or C++ libraries.
- Sufficient for the contest demo scale and can fall back to keyword retrieval without breaking RAG.

It is not a full production ANN database. It is a target-safe embedded database baseline until a stronger service passes LoongArch/Kylin verification. The pure JSON vector index remains available as an even smaller fallback.

## Why Chroma Is Not Target-Compatible As The Main Route

Sources:

- <https://github.com/chroma-core/chroma>
- <https://pypi.org/project/chroma-hnswlib/>
- <https://github.com/chroma-core/hnswlib>

Chroma itself is mature and popular. Its repository describes Chroma as open-source data infrastructure for AI and shows a simple `pip install chromadb` client/server workflow. The problem is not Chroma's product direction; the problem is target-environment dependency compatibility.

### Evidence From Upstream Packages

Chroma depends on the HNSW native indexing layer through `chroma-hnswlib`, Chroma's fork of `hnswlib`. Upstream describes that dependency as a C++/Python library for approximate nearest neighbors.

The `chroma-hnswlib` PyPI release provides prebuilt wheels for common architectures such as:

- Windows x86-64
- manylinux x86-64
- manylinux ARM64 / AArch64
- macOS ARM64
- macOS x86-64

The PyPI file list does not provide a LoongArch wheel. On loongarch64, pip therefore cannot use a compatible prebuilt wheel and must fall back to source build. That source build depends on native compiler/toolchain behavior, Python packaging support, and hnswlib compatibility on LoongArch.

### Evidence From Our Target VM

The competition VM is:

```text
Architecture: loongarch64
OS: Kylin Linux Advanced Server V11
Docker: 24.0.9
Base image: cr.loongnix.cn/library/python:3.11
```

Observed installation failures:

- `chromadb>=0.5,<2` attempted to install `chromadb-1.5.9` and failed while building dependencies with `OSError: [Errno 22] Invalid argument`.
- Pinning `chromadb==0.5.23` still failed when building `chroma-hnswlib`.
- This failure occurred before application runtime, so it blocks Docker image build and cannot be treated as a normal runtime fallback.

### Delivery Decision

Chroma must not be installed in the default Docker image and must not be described as the competition main vector database.

Allowed use:

```text
RAG_VECTOR_STORE=chroma
INSTALL_CHROMA=true
```

Only for non-LoongArch environments or a future LoongArch image where `chromadb` and `chroma-hnswlib` installation has been proven.

Replacement:

```text
RAG_VECTOR_STORE=sqlite
```

The SQLite vector index keeps the same application-level semantics:

- approved-only indexing
- no `pending_review` leakage
- document deletion cleanup
- hash or remote embeddings
- fallback to keyword retrieval when vector search fails

This preserves the RAG retrieval contract without depending on unsupported native wheels.

## Candidate Ranking

| Rank | Candidate | Main-route status | Why |
| --- | --- | --- | --- |
| P0 | Built-in SQLite vector index | Keep now | Target-safe embedded database using Python stdlib `sqlite3`, no external service. |
| P0 fallback | Built-in JSON vector index | Keep | Pure Python fallback if SQLite is unavailable. |
| P1 | PostgreSQL + pgvector | Best mature replacement candidate | Mature Postgres extension, ACID storage, exact and ANN search, source build route. Needs target VM proof. |
| P2 | sqlite-vec | Best embedded experiment | Single C extension and easy local-file deployment. Less mature, must compile on LoongArch. |
| P3 | Qdrant | Not main route | Official supported CPU architectures are amd64 and arm64, not LoongArch. |
| P4 | Milvus | Not two-day route | Mature and scalable, but heavy Go/C++ service stack and Docker script path; architecture proof required. |
| P4 | Weaviate | Not two-day route | Mature Go service with Docker/Kubernetes deployment; architecture proof required. |

## pgvector Assessment

Source: <https://github.com/pgvector/pgvector>

Observed from the official README:

- It is an open-source vector search extension for PostgreSQL.
- It supports exact and approximate nearest neighbor search, cosine/L2/inner product distance, HNSW, IVFFlat, and normal PostgreSQL client access.
- Linux installation uses source compilation with `make` and `make install`, and supports PostgreSQL 13+.

Why it is the best mature candidate:

- It is built on PostgreSQL, which fits production-style persistence, SQL filtering, backups, and transactions.
- Our current chunk metadata maps naturally to SQL columns plus a vector column.
- It avoids Python native wheel problems in the application process.
- It gives a credible production upgrade path for the answer defense.

Risks:

- We have not yet proved PostgreSQL server, development headers, compiler toolchain, and pgvector extension compilation on the actual LoongArch/Kylin VM.
- It adds operational complexity compared with the current JSON store.
- It requires a new adapter and migration/import script, so it should not replace JSON until a target smoke test passes.

Required target test:

```bash
psql --version
pg_config --version
git clone --branch v0.8.3 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
createdb repair_knowledge
psql -d repair_knowledge -c "CREATE EXTENSION vector;"
psql -d repair_knowledge -c "CREATE TABLE vector_smoke (id text primary key, embedding vector(3));"
psql -d repair_knowledge -c "INSERT INTO vector_smoke VALUES ('a','[1,2,3]'),('b','[3,2,1]');"
psql -d repair_knowledge -c "SELECT id FROM vector_smoke ORDER BY embedding <-> '[1,2,2]' LIMIT 1;"
```

If this passes, implement `RAG_VECTOR_STORE=pgvector` as an optional adapter. Do not remove JSON.

## sqlite-vec Assessment

Sources:

- <https://github.com/asg017/sqlite-vec>
- <https://alexgarcia.xyz/sqlite-vec/installation.html>

Observed from official docs:

- Provides vector search as a SQLite extension.
- Offers Python, Node.js, Ruby, Rust, Go, Datasette, and sqlite-utils bindings.
- Precompiled extensions exist, but the important target fact is that it is a single `sqlite-vec.c` / `sqlite-vec.h` pair and can be compiled for different platforms or statically linked.

Why it is attractive:

- Much closer to our current single-machine, file-based deployment model than pgvector.
- SQLite is already part of Python stdlib, and the extension model keeps operations simple.
- It can become a middle step between JSON vectors and a service database.

Risks:

- Version is still pre-1.0.
- We still need LoongArch compilation proof.
- Python package wheels may not support loongarch64, so the safe route is compiling the extension from source and loading it with `sqlite3`.

Required target test:

```bash
sqlite3 --version
cc --version
git clone https://github.com/asg017/sqlite-vec.git
cd sqlite-vec
# Follow upstream compile instructions for producing sqlite-vec shared extension.
sqlite3 :memory: "select load_extension('./sqlite_vec'); select vec_version();"
```

If this passes, implement `RAG_VECTOR_STORE=sqlite_vec` as an embedded optional adapter. Do not present it as more mature than pgvector.

## Qdrant Assessment

Source: <https://qdrant.tech/documentation/operations/installation/>

Observed from official docs:

- Qdrant is production-grade and supports Docker/Kubernetes/binary deployment.
- Official installation requirements list supported CPU architectures as x86_64/amd64 and AArch64/arm64.
- LoongArch is not listed.

Decision:

Do not use Qdrant as the target main route. It can remain an architecture reference for payload filtering, HNSW, snapshots, and API style, but adopting it would violate the target-environment evidence rule unless we build and verify a LoongArch binary ourselves.

## Milvus Assessment

Sources:

- <https://github.com/milvus-io/milvus>
- <https://milvus.io/docs/install_standalone-docker.md>

Observed from official docs:

- Milvus is a mature high-performance vector database written in Go/C++.
- It supports standalone mode and Docker installation scripts.
- It is designed for large-scale ANN search and distributed/cloud-native scenarios.

Decision:

Not suitable for the two-day competition main route. It is too heavy operationally, has native components, and still needs LoongArch image/build proof.

## Weaviate Assessment

Sources:

- <https://github.com/weaviate/weaviate>
- <https://docs.weaviate.io/deploy/installation-guides/docker-installation>

Observed from official docs:

- Weaviate is a mature cloud-native vector database that supports vector search, structured filtering, RAG, reranking, multi-tenancy, replication, and Docker/Kubernetes deployment.

Decision:

Not suitable for the target main route today. It is a capable platform, but we have no LoongArch Docker/binary proof and it would add more infrastructure than this project needs for the contest.

## Implementation Recommendation

Use a three-layer vector-store policy:

```text
RAG_VECTOR_STORE=sqlite     # default, target-safe delivery route
RAG_VECTOR_STORE=json       # smallest pure-file fallback
RAG_VECTOR_STORE=pgvector   # next mature route after target proof
RAG_VECTOR_STORE=sqlite_vec # embedded experiment after target proof
RAG_VECTOR_STORE=chroma     # non-LoongArch optional compatibility
```

Adapter contract should stay stable:

```python
sync_chunks(chunks: list[dict]) -> None
delete_document(document_id: str) -> None
search_similar_chunks(query: str, top_k: int) -> list[dict]
status() -> dict
```

No retrieval ranking algorithm should depend on a specific vector database. Metadata filters, approved-only isolation, evidence fields, and fallback behavior must remain in the application layer.

## Next Action

Target VM verification order:

1. Check PostgreSQL availability: `psql`, `pg_config`, server start, local database creation.
2. Compile and load pgvector from source.
3. If pgvector fails, compile sqlite-vec from source.
4. Only after one passes, add the optional adapter and tests.
5. Keep SQLite vector index as the default until a stronger target-verified vector service is committed.
