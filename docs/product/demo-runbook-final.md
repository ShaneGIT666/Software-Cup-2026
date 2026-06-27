# 最终演示 Runbook

版本日期：2026-06-27

## 1. 启动前准备

1. 确认 `.env` 不提交到仓库。
2. 如果需要真实 LLM，运行初始化脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\init-config.ps1
```

Linux / Kylin / LoongArch：

```bash
bash scripts/init-config.sh
```

3. 启动后端和前端，或使用 Docker / FastAPI 静态托管路径。

## 2. 演示主线一：检修助手

1. 打开系统，默认进入“检修助手”。
2. 展示首次使用引导：描述故障 -> 查看依据 -> 生成指引 -> 复核修正 -> 提交经验。
3. 点击“使用演示样例”，填入设备型号、故障现象和检修等级。
4. 点击“开始诊断”。
5. 展示“参考依据”，强调系统仅使用已审核资料。
6. 如有图片，点击“图片诊断”，展示 OCR、视觉现象、识别部件和图片识别线索。
7. 点击“生成智能检修建议”，展示：
   - 初步判断。
   - 检查步骤。
   - 维修步骤。
   - 安全提醒。
   - 验收标准。
   - 引用来源。
   - 不确定信息。
8. 打开“回答标注 / 修正”，提交一条修正，说明默认进入待审核。
9. 在“提交处理经验”填写故障原因、处理方法、处理结果并提交。

## 3. 演示主线二：管理中心

1. 切换到“管理中心”。
2. 展示“资料入库”：上传维修手册、PDF、Office、Markdown 或图片资料。
3. 展示图片资产分析状态：待分析、分析中、已完成、降级次数。
4. 展示“待审核内容”：审核资料片段、维修案例或回答修正。
5. 展示“审核记录”：说明 reviewer、时间、动作和状态变化可追溯。
6. 展示“知识关系图”：
   - 摘要统计。
   - 图例。
   - SVG 网络图。
   - 点击节点显示详情。
   - 典型关系路径。
   - approved-only 说明。

## 4. 演示主线三：系统状态

1. 切换到“系统状态”。
2. 展示当前运行模式、模型服务、OCR、多模态、向量检索和离线兜底状态。
3. 展示初始化配置命令：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\init-config.ps1
```

```bash
bash scripts/init-config.sh
```

4. 说明真实 LLM 使用 OpenAI-compatible 配置接入，Key 只写本地 `.env`，不通过 Web 保存。
5. 说明 LoongArch / Kylin 部署策略：Docker 优先，venv + FastAPI 静态托管兜底。

## 5. 关键接口

```text
GET  /api/health
GET  /api/providers/status
POST /api/search
POST /api/rag/answer
POST /api/multimodal/diagnosis
POST /api/rag/feedback
PATCH /api/rag/feedback/{id}/review
POST /api/knowledge/documents/async
GET  /api/review/items
GET  /api/knowledge/graph
```

## 6. 答辩边界口径

- 图片能力当前是“图片识别线索进入检索上下文”，不夸大为生产级图文向量检索。
- 知识关系图是轻量知识关系网络原型，不宣称完整工业图数据库平台。
- mock、hash、fallback 是现场稳定性兜底，不作为真实模型能力宣传。
- 真实 LLM 能力以目标环境 provider 验证为准。

## P0 补充演示点：PDF 页面视觉资产

管理中心上传官方“摩托车发动机维修手册”后，若 MinerU 超时或未提取到图片 assets，资料卡应显示“PDF 页面视觉资产已生成”，且图片资产片段数量大于 0。随后进入片段审核入口，可看到 `PDF 页面视觉资产` 类型片段。

讲解口径：这是 PDF 页面级视觉资产 fallback，用于保证图示页进入审核和知识沉淀链路；它不替代真实 OCR/多模态图像理解，正式使用前仍需审核。
