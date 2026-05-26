# 软件功能测试报告

项目名称：基于多模态大模型技术的设备检修知识检索与作业系统  
测试日期：2026-05-25  
测试范围：本地 MVP 功能闭环、后端接口、前端生产构建、演示主流程  
测试环境：Windows 本地开发环境，FastAPI 后端，Vue 3 + Vite 前端

## 1. 测试结论

当前系统已通过本地自动化回归测试和前端生产构建验证，具备比赛 MVP 演示条件。

结论摘要：
1. 后端接口测试通过，覆盖健康检查、检索、上传、资料入库、RAG、案例审核、多模态分析和轻量知识关系网络。
2. 前端生产构建通过，核心工作台可编译为静态资源。
3. 当前真实 OpenAI/Anthropic 多模态联网调用尚未验收，默认使用 mock provider 保证演示连续性。
4. 官方 LoongArch + 银河麒麟环境暂未开放，国产化实测暂未完成。

## 2. 测试对象

后端接口：
1. `GET /api/health`
2. `POST /api/search`
3. `POST /api/rag/answer`
4. `POST /api/knowledge/graph`
5. `POST /api/uploads`
6. `POST /api/knowledge/documents`
7. `POST /api/knowledge/documents/{document_id}/analyze`
8. `GET /api/knowledge/documents`
9. `GET /api/knowledge/documents/{document_id}`
10. `GET /api/knowledge/documents/{document_id}/chunks`
11. `DELETE /api/knowledge/documents/{document_id}`
12. `POST /api/cases`
13. `GET /api/cases`
14. `PATCH /api/cases/{case_id}/review`
15. `GET /api/workflows/{workflow_id}`

前端页面：
1. 检索输入区
2. 结果列表区
3. 标准作业流程区
4. 资料入库区
5. RAG 辅助建议区
6. 知识关系网络区
7. 案例提交区
8. 案例审核区

## 3. 自动化测试

执行命令：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-backend-tests.ps1
```

预期结果：

```text
33 passed
```

覆盖场景：

| 编号 | 测试项 | 预期 |
| --- | --- | --- |
| T-BE-001 | 健康检查 | 返回 `success=true` 和 `status=ok` |
| T-BE-002 | 正常检索 | 返回结果、命中词和 `scoreBreakdown` |
| T-BE-003 | 空查询 | 返回 `400`，不生成伪结果 |
| T-BE-004 | RAG mock 回答 | 返回 answer、recommendedActions 和 citations |
| T-BE-005 | OpenAI/Anthropic provider fallback | 未配置 Key 时降级到 mock |
| T-BE-006 | 工作流查询 | 返回标准作业步骤、工具、安全提醒和验收标准 |
| T-BE-007 | 现场文件上传 | 校验扩展名、MIME、空文件、大小上限和上传目录隔离 |
| T-BE-008 | 案例提交审核闭环 | 提交后待审核，审核通过后可检索命中 |
| T-BE-009 | 非法审核 action | 返回错误且不改变案例状态 |
| T-BE-010 | 资料入库 | TXT/Markdown 可生成 chunks 并进入检索 |
| T-BE-011 | 资料详情与删除 | 可查询详情、chunks，删除后不再命中 |
| T-BE-012 | 图片资料多模态分析 | 图片上传后可 mock 分析并生成可检索 chunks |
| T-BE-013 | 多模态 provider fallback | 真实 provider 未配置时自动降级 |
| T-BE-014 | 多模态分析结果进入 RAG | 分析 chunks 可出现在 citations 中 |
| T-BE-015 | 轻量知识关系网络 | 返回设备、故障、资料/案例/流程节点和关系 |

## 4. 前端构建测试

执行命令：

```powershell
cd frontend
npm.cmd run build
```

预期结果：构建通过，生成 `frontend/dist/`。

已知非阻塞提示：
1. Rollup 对 `@vueuse/core` 部分 pure annotation 的提示。
2. Vite chunk size warning。

上述提示不影响当前 MVP 演示。后续若进入生产化阶段，可通过代码分包或手动 chunk 配置优化。

## 5. 手动功能验收

验收路径：
1. 启动 `start-dev.bat`。
2. 打开 `http://localhost:5173`。
3. 使用默认设备型号和故障描述执行检索。
4. 查看检索结果中的来源、命中原因和评分解释。
5. 生成 RAG 辅助建议，确认 citations 存在。
6. 查看标准作业流程、安全提醒和验收标准。
7. 上传 TXT/Markdown 资料并确认 chunk 数。
8. 上传官方 PDF 或图片资料，执行 mock 多模态分析。
9. 再次检索，确认入库资料进入结果和 RAG citations。
10. 生成知识关系网络，确认节点和关系数量。
11. 提交维修案例，审核通过，再次检索命中新案例。

## 6. 测试数据隔离

自动化测试必须使用以下环境变量隔离运行时数据：

```text
APP_EXAMPLES_DIR
APP_KNOWLEDGE_DIR
APP_UPLOAD_DIR
```

测试不得污染：
1. `data/examples/repair-cases.json`
2. `data/uploads/`
3. `data/knowledge/`
4. 官方样例 PDF 文件

## 7. 未完成或待实测项

| 项目 | 当前状态 | 后续动作 |
| --- | --- | --- |
| LoongArch + 银河麒麟实测 | 官方环境未开放 | 环境开放后执行部署验证清单 |
| 真实 OpenAI/Anthropic 多模态调用 | 已有适配层，未联网验收 | 使用小样本单独验证 Key、费用、超时和 fallback |
| 生产级 OCR | 未实现 | 后续评估 PaddleOCR、MinerU、Docling |
| 向量 RAG | 未实现 | 后续评估 Chroma/Qdrant，不影响当前 MVP |
| 完整知识图谱 | 未实现 | 当前仅为轻量关系网络原型 |

## 8. 风险说明

1. 当前系统不能宣称已完成生产级跨模态语义检索。
2. 当前多模态能力默认可通过 mock provider 演示，真实云 API 依赖网络、Key、费用和模型限制。
3. 当前知识关系网络用于比赛演示和可解释性展示，不是生产级图数据库。
4. 国产化部署是官方硬约束，必须在官方环境开放后补充实测证据。
