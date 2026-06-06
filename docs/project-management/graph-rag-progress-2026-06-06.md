# Graph RAG 与轻量知识图谱交接说明

更新时间：2026-06-06

用途：给后续 Coding Agent、协作者和人工复审者快速理解“知识图谱 + RAG”本轮新增能力。本文档自包含，不依赖聊天记录。

## 1. 本轮目标

本轮不是引入 Neo4j、GraphRAG 框架或生产级图数据库，而是在现有 FastAPI + Vue + JSON 轻量架构内，把“检索结果关系展示”升级为“轻量知识图谱 / Graph RAG 证据链”。

目标链路：

```text
用户输入设备型号和故障现象
-> /api/search 做可解释检索
-> /api/knowledge/graph 构建当前查询子图
-> /api/rag/answer 把 citations + graphContext 一起交给 LLM/mock
-> 前端展示 RAG 回答、引用来源、图谱节点、关系证据和完善建议
```

## 2. 新增后端能力

### 2.1 查询子图

接口：

```http
POST /api/knowledge/graph
```

请求体沿用 `SearchRequest`：

```json
{
  "deviceModel": "摩托车发动机",
  "faultText": "无法启动 火花塞",
  "inputType": "text",
  "topK": 6
}
```

响应新增字段：

1. `mode=query`：表示当前查询子图。
2. `generatedAt`：图谱生成时间。
3. `stats`：节点数、关系数、节点类型统计、关系类型统计。
4. `focusNodeIds`：当前设备、故障和核心证据节点。
5. `recommendations`：资料补充或图谱完善建议。
6. node `properties`：来源、置信度、documentId、chunkId 等扩展属性。
7. edge `confidence`：关系置信度。

### 2.2 全局图谱

接口：

```http
GET /api/knowledge/graph
POST /api/knowledge/graph/rebuild
```

行为：

1. `GET /api/knowledge/graph` 返回缓存的全局图谱；缓存不存在时自动构建。
2. `POST /api/knowledge/graph/rebuild` 强制基于 seed 数据、入库资料、chunks、案例和流程重建图谱。
3. 运行期缓存写入 `data/knowledge/knowledge-graph.json`，该文件不得提交 Git。

### 2.3 Graph RAG 上下文

`POST /api/rag/answer` 请求体新增字段：

```json
{
  "includeGraphContext": true
}
```

默认值为 `true`。

响应新增：

```json
{
  "graphContext": {
    "enabled": true,
    "summary": "围绕当前查询生成 N 个知识节点、M 条关系",
    "nodeCount": 12,
    "edgeCount": 18,
    "paths": [
      {
        "source": "无法启动 火花塞",
        "sourceType": "fault",
        "relation": "证据支持",
        "target": "官方摩托车发动机维修手册",
        "targetType": "document",
        "evidence": "命中入库资料片段",
        "confidence": 0.86
      }
    ]
  }
}
```

真实 OpenAI-compatible / Anthropic prompt 会包含“知识图谱关系上下文”，要求模型基于 citations 和图谱关系回答；mock fallback 也会返回图谱规模提示，保证弱网演示不断链。

## 3. 前端变化

文件：

1. `frontend/src/api.ts`
2. `frontend/src/App.vue`
3. `frontend/src/components/KnowledgeGraphPanel.vue`

能力：

1. 知识图谱面板标题升级为“知识图谱 / Graph RAG 证据链”。
2. 支持“当前查询子图”“全局图谱”“重建图谱”三个操作。
3. 显示节点/关系数量、查询/全局模式、节点类型统计。
4. 展示关系证据和图谱完善建议。
5. RAG 面板可继续使用原接口，新增 `graphContext` 字段向后兼容，不破坏旧 UI。

## 4. 测试与验证

后端测试：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-backend-tests.ps1
```

最新结果：

```text
81 passed
```

新增覆盖：

1. 全局图谱 overview 和 rebuild。
2. RAG 响应包含 `graphContext`。
3. 真实 OpenAI-compatible mock 测试确认 prompt 包含“知识图谱关系上下文”“图谱规模”和 `G1` 路径。

前端构建：

```powershell
cd frontend
.\node_modules\.bin\vue-tsc.cmd -b
.\node_modules\.bin\vite.cmd build --configLoader runner
```

最新结果：通过。

说明：普通 `npm.cmd run build` 在当前 Windows 沙箱中可能因 Vite 写 `node_modules/.vite-temp` 或 `frontend/dist/assets` 权限失败；具备正常写权限的环境可直接构建。当前仍有 chunk size warning，不阻塞比赛演示。

## 5. 官方摩托车手册初步召回测算

资料：`E:/Download/Downloads/摩托车发动机维修手册.pdf`

入库结果：

```text
parser=pypdf
status=indexed
chunkCount=42
```

12 条中文故障查询，资料源级召回：

```text
Recall@1 = 8/12 = 66.67%
Recall@3 = 12/12 = 100.00%
Recall@5 = 12/12 = 100.00%
```

RAG 引用命中：

```text
CitationHit@5 = 12/12 = 100.00%
```

解释：

1. 这是“资料源级召回”，即 TopK 里命中官方手册任意 chunk 即算成功。
2. 这不是人工标注页码/chunk 级召回。
3. 可用于说明当前检索和 RAG 引用闭环可用。
4. `Recall@1=66.67%` 说明 Top1 精排仍有优化空间，后续可做 BM25、真实 embedding 或 reranker。

## 6. 风险口径

可以说：

1. 已实现轻量知识图谱。
2. 已实现 Graph RAG 证据链。
3. RAG prompt 会包含 citations 和图谱关系上下文。
4. 图谱可覆盖设备、故障、资料、chunk、案例、流程、术语和 provider。

不要说：

1. 已完成生产级知识图谱。
2. 已完成 Neo4j 图数据库。
3. 已完成复杂多跳图推理。
4. 当前 hash embedding 是真实语义 embedding。

## 7. 后续建议

1. 做 20 到 30 条人工标注查询集，标注期望页码或 chunk，输出严格 `Recall@K`。
2. 优化 Top1 排序，优先考虑 BM25 或真实 embedding，不要急于引入重型图数据库。
3. 如果答辩强调创新点，可展示“检索结果 -> 图谱证据链 -> RAG 回答”的完整路径。
4. 若后续引入 Neo4j 或 GraphRAG，应作为二阶段升级，并保持当前 JSON fallback 可用。

## 8. 2026-06-06 追加：演示种子数据扩展

为避免比赛演示显得只覆盖“发动机启动困难”单一场景，本轮继续扩展 seed 数据，仍保持轻量 JSON 架构。

新增数据：

1. `data/examples/devices.json`：从 3 台设备扩展到 6 台，新增润滑发动机、电气启动控制系统、链传动执行机构。
2. `data/examples/manuals.json`：从 5 条手册片段扩展到 8 条，新增润滑系统、电气控制、链传动检修片段。
3. `data/examples/workflows.json`：从 3 条标准作业流程扩展到 6 条。
4. `data/examples/repair-cases.json`：从 4 条维修案例扩展到 7 条，新增 3 条已审核案例。

新增流程：

| workflowId | 场景 | 演示关键词 |
| --- | --- | --- |
| `wf-004` | 润滑不足与机油压力异常 | 机油压力低、润滑不足、高温报警 |
| `wf-005` | 电气系统无法上电 | 无法上电、保险丝、主继电器、线束接插件 |
| `wf-006` | 链传动异响与张紧度 | 链条张紧、传动异响、润滑 |

新增测试覆盖：

1. `test_expanded_seed_workflows_are_searchable`：验证 3 个新增场景均可被 `/api/search` 命中，并带出对应 `workflowId`。
2. `test_global_graph_includes_expanded_seed_workflows`：验证全局知识图谱包含新增流程和场景节点。

最新后端测试结果：

```text
83 passed
```

演示口径：当前系统已有 6 条标准作业流程，可覆盖启动、排气、异响、润滑、电气上电、链传动等典型检修场景；这些流程均可通过检索结果、RAG citations 和知识图谱证据链串联展示。
