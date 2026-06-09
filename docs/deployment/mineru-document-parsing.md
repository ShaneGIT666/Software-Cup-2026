# MinerU 文档解析接入说明

更新时间：2026-06-09

本文记录 MinerU 在“设备检修知识检索与作业辅助系统”中的安装、配置、运行链路和风险边界。目标是把 PDF / DOCX / PPTX / XLSX 等资料解析从普通文本 fallback 提升为可用于准生产原型的主链路，同时保留失败降级，避免资料上传流程被重依赖阻断。

## 1. 当前结论

Windows 本地开发环境已安装并验证 MinerU：

```powershell
.\backend\.venv\Scripts\mineru.exe --version
# mineru, version 3.2.3
```

项目内 `parse_document()` 小样本已验证可走真实 MinerU 解析：

```text
parser=mineru
status=parsed
fallback=False
```

后端完整 API 测试和前端构建已通过：

```powershell
.\backend\.venv\Scripts\python.exe -m pytest tests\test_backend_api.py
# 70 passed

cd frontend
npm.cmd run build
# built successfully
```

## 2. 安装方式

MinerU 依赖较重，不放入最小后端依赖链路。需要真实文档解析能力的机器单独安装：

```powershell
cd E:\Software\Software-Cup-2026
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-mineru.txt
```

依赖清单：

```text
backend/requirements-mineru.txt
```

当前锁定：

```text
mineru[all]==3.2.3
```

## 3. 配置项

`.env.example` 已补充以下配置：

```env
MINERU_ENABLED=true
MINERU_BACKEND=pipeline
MINERU_LANG=ch
MINERU_TIMEOUT_SECONDS=180
MINERU_API_URL=
```

字段说明：

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| `MINERU_ENABLED` | `true` | 是否启用 MinerU 主解析链路；关闭后自动走 pypdf/mock fallback |
| `MINERU_BACKEND` | `pipeline` | 默认使用更通用、CPU 友好的 pipeline backend |
| `MINERU_LANG` | `ch` | 中文资料默认语言 |
| `MINERU_TIMEOUT_SECONDS` | `180` | 单文件解析超时，超时后自动降级 |
| `MINERU_API_URL` | 空 | 可接入外部 MinerU FastAPI 服务；为空时 MinerU CLI 会临时启动本地服务 |

## 4. 主链路行为

资料上传入口仍是：

```text
POST /api/knowledge/documents
```

解析路由：

```text
PDF / DOCX / PPTX / XLSX
-> parser_router
-> MinerU adapter
-> raw_parse_result.json / parsed.md / assets
-> 生成知识片段 review_status=pending_review
-> 审核通过前不进入正式 RAG 检索和 Chroma 同步
```

图片资料仍按赛题多模态要求走 OCR / 多模态分析链路，不强行交给 MinerU。

## 5. 产物保存

每次资料上传后，解析产物保存到：

```text
data/knowledge/parsed/{document_id}/
```

目录结构：

```text
raw_parse_result.json
parsed.md
assets/
```

说明：

1. `raw_parse_result.json` 保存统一后的解析结果、MinerU 输出文件索引和运行日志摘要。
2. `parsed.md` 保存可读 Markdown，用于人工审核和后续切分。
3. `assets/` 保存 MinerU 输出的图片等资源副本，避免审核阶段依赖临时目录。

## 6. 降级策略

MinerU 失败不会中断上传接口：

| 场景 | 行为 |
| --- | --- |
| 未安装 MinerU | PDF 走 pypdf；Office 走 mock parser |
| `MINERU_ENABLED=false` | 跳过 MinerU，直接 fallback |
| MinerU 超时 | 终止进程树，fallback |
| MinerU 返回非 0 | 记录 `fallbackReason`，fallback |
| MinerU 无可用 Markdown/JSON | 记录 `fallbackReason`，fallback |

fallback 后生成的资料不会直接污染正式知识库；片段默认仍进入 `pending_review` 或资料状态保持 `needs_parser`。

## 7. 已知风险

1. MinerU 依赖体积大，首次安装会引入 Torch、OpenCV、Gradio 等大量包。
2. 首次解析会启动临时 `mineru-api`，小 DOCX 样本在当前 Windows 环境约 29 秒。
3. LoongArch / Kylin 环境尚未完整验收 MinerU 真实依赖，生产部署需单独验证。
4. 当前采用 CLI adapter，后续如固定 MinerU FastAPI 服务，可通过 `MINERU_API_URL` 接入。

## 8. 验收命令

```powershell
.\backend\.venv\Scripts\mineru.exe --version
.\backend\.venv\Scripts\python.exe -m pytest tests\test_backend_api.py
cd frontend
npm.cmd run build
```

如需关闭真实解析验证 fallback：

```powershell
$env:MINERU_ENABLED="false"
.\backend\.venv\Scripts\python.exe -m pytest tests\test_backend_api.py -k "parser or knowledge_document_upload"
```
