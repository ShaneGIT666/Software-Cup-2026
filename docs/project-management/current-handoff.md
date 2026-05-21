# 当前开发交接说明

更新时间：2026-05-21  
适用对象：后续 Coding Agent、协作者、人工复审人员

## 1. 当前状态

项目仍以完成中国软件杯 A1 赛题为目标，当前主线是“可演示、可解释、可抗追问”的 MVP。官方 LoongArch + 银河麒麟环境暂未开放，因此国产化实测暂缓，但硬约束不能删除。

当前分支：`main`

本轮新增能力：
1. 多模态资料分析增强层。
2. 轻量知识关系网络。
3. 前端资料入库与知识关系展示面板。
4. 后端测试和 API/演示/开源引用文档同步。

官方样例资料：

```text
E:/Download/Downloads/摩托车发动机维修手册.pdf
```

该 PDF 仅作为本地演示/测试输入，不得提交进 Git。

## 2. 已实现能力

后端新增或扩展：
1. `POST /api/knowledge/documents` 支持 `pdf/txt/md/jpg/jpeg/png/webp`。
2. `POST /api/knowledge/documents/{document_id}/analyze` 对 PDF/图片资料执行多模态分析。
3. `backend/app/multimodal_adapter.py` 支持 `mock/openai/anthropic` provider。
4. 多模态分析结果会生成本地 `document` chunks，可进入搜索和 RAG citations。
5. `POST /api/knowledge/graph` 基于当前查询和检索结果生成轻量知识关系网络。
6. `backend/app/knowledge_graph.py` 将设备、故障、资料、案例、流程、来源和 provider 组织为节点与关系。

前端新增或扩展：
1. `KnowledgePanel.vue` 支持图片资料上传、待多模态分析状态、多模态分析按钮和分析摘要展示。
2. `KnowledgeGraphPanel.vue` 展示当前查询的轻量知识关系网络。
3. `App.vue` 在检索后自动刷新知识关系网络，也支持手动刷新。

配置更新：
1. `.env.example` 新增 `MULTIMODAL_PROVIDER`、`MULTIMODAL_TIMEOUT_SECONDS`。
2. `.env.example` 补充 OpenAI/Anthropic provider 相关变量示例。

## 3. 验证结果

后端测试：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-backend-tests.ps1
```

结果：

```text
33 passed
```

前端构建：

```powershell
cd frontend
npm.cmd run build
```

结果：通过。

已知非阻塞 warning：
1. Rollup 对 `@vueuse/core` 中部分 pure annotation 的提示。
2. Vite chunk size warning。

## 4. 风险边界

必须准确表述：
1. 当前多模态真实 API 适配是工程接口层，尚未用真实 OpenAI/Anthropic Key 做端到端联网验收。
2. 当前知识关系网络是轻量知识图谱原型，不是生产级图数据库。
3. 当前 RAG 仍以本地关键词检索 + citations + provider fallback 为主，不是完整向量 RAG。
4. 官方 LoongArch + 银河麒麟环境未开放，尚无真实国产化部署证明。
5. 不要提交官方 PDF、`data/uploads/`、`data/knowledge/`、`.env`、`node_modules/`、`dist/`、`.venv/`。

不要在答辩或文档中夸大为：
1. 已完成生产级 OCR。
2. 已完成完整知识图谱。
3. 已完成跨模态语义检索。
4. 已完成国产化环境验证。
5. 已完成真实云模型稳定联调。

## 5. 推荐演示路径

1. 启动 `start-dev.bat`。
2. 打开 `http://localhost:5173`。
3. 先用 TXT/Markdown 资料演示稳定入库、检索、RAG 引用闭环。
4. 上传官方 PDF 或现场故障图片，展示 `待多模态分析` 状态。
5. 点击“多模态分析”，默认走 `mock` provider，生成摘要、关键部件、故障现象和知识片段。
6. 再次搜索“发动机 / 火花塞 / 启动困难”等关键词。
7. 展示搜索结果、RAG citations、标准作业流程和知识关系网络。
8. 提交维修案例，审核通过，再次检索命中新案例。

## 6. 下一步建议

优先级从高到低：
1. 准备正式软件功能测试报告。
2. 编写 7 分钟以内演示视频脚本和 PPT 大纲。
3. 用官方 PDF 做一次本地演示录屏，记录 fallback 路径。
4. 如需展示真实模型能力，单独做 OpenAI/Anthropic 小样本联网验收。
5. 官方环境开放后，第一时间执行 LoongArch + 银河麒麟部署验证并补充证据截图。

## 7. 后续 Agent 接手规则

1. 先读本文，再读 `docs/requirements/official-problem-baseline.md`。
2. 开始前执行 `git status --short --branch`。
3. 不使用 `git reset --hard` 或 `git checkout --` 回滚用户/协作者改动。
4. 不引入 PaddleOCR、MinerU、Docling、LlamaIndex、Chroma、Qdrant、Neo4j 等重依赖，除非先完成小样本验证和风险评审。
5. 任何 API、数据状态、演示路径或风险边界变化，都必须同步更新本文。
