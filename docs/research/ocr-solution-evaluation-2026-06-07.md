# OCR 开源方案评估与引入建议

更新日期：2026-06-07

本文用于补充 `open-source-architecture-research.md` 中的 OCR 二阶段规划，目标是在不破坏当前比赛演示闭环的前提下，选择一个成熟、开源、可降级、可在 LoongArch/Kylin 风险下解释清楚的 OCR 引入路线。

## 1. 结论

推荐采用“两层 OCR 路线”：

1. 第一落地优先级：`RapidOCR` / `PaddleOCR PP-OCRv5` 做图片与扫描件文字识别。
2. 第二增强优先级：`Docling` 或 `MinerU` 做复杂 PDF 的版式解析、表格、阅读顺序和 Markdown/JSON 输出。
3. 比赛现场兜底：保留当前 `mock` 多模态分析和 `pypdf` 文本 PDF 解析，不让 OCR 依赖安装失败影响主链路。

建议工程默认先接 `RapidOCR` 作为本地 OCR provider，再预留 `PaddleOCR` provider。原因是 RapidOCR 基于 ONNX Runtime 等推理后端，工程集成更轻；PaddleOCR 能力更完整，适合作为 Windows 本地或 x86 环境的高质量验证方案；Docling/MinerU 更像“文档解析引擎”，不应作为第一步 OCR 依赖直接塞进主 requirements。

## 2. 候选方案对比

| 方案 | 适合场景 | 优点 | 风险 | 建议 |
| --- | --- | --- | --- | --- |
| RapidOCR | 图片、扫描件的通用文字识别 | 轻量，支持 ONNX Runtime/OpenVINO/MNN/PaddlePaddle/TensorRT/PyTorch 等后端，Apache-2.0 | LoongArch 上 ONNX Runtime wheel/编译仍需实测 | 第一优先级，小样本验证 |
| PaddleOCR | 中文 OCR、工业图片文字、扫描手册、表格/版式扩展 | PP-OCRv5 支持 100+ 语言，PP-StructureV3 支持 PDF/图片转 Markdown/JSON，Apache-2.0 | Paddle/PaddleX 依赖更重，LoongArch/Kylin 安装风险较高 | 高质量方案，先做可选依赖 |
| Docling | PDF/DOCX/PPTX/XLSX/图片转结构化数据 | MIT，支持 OCR、版面、表格、阅读顺序、Markdown/JSON，本地执行 | 官方说明支持 x86_64/arm64，未覆盖 LoongArch；依赖较多 | 复杂文档增强，不作为第一步 |
| MinerU | 复杂 PDF/Office/图片转 RAG 友好 Markdown/JSON | 面向 LLM/RAG，自动识别扫描 PDF 并启用 OCR，支持 109 语言 | 自定义开源许可证；模型和依赖较重 | 离线文档解析专项验证 |
| Tesseract | Linux 传统 OCR、命令行兜底 | Apache-2.0，系统包成熟，支持中文 traineddata | 中文/复杂版式效果通常弱于 Paddle 系方案 | LoongArch 系统包兜底备选 |

## 3. 推荐架构

在后端新增一个可替换 OCR provider 层，不直接把某个 OCR 库写死进 `knowledge.py`：

```text
资料上传
  -> pypdf 尝试提取文本
  -> 若文本为空或疑似扫描件，状态置为 needs_ocr
  -> 用户点击 OCR 分析
  -> OCRProvider 识别文本
  -> 复用现有 chunk 切分与 documents/chunks 存储
  -> 进入 search / rag / graph 现有链路
```

建议接口：

```python
class OCRProvider(Protocol):
    name: str

    def recognize(self, file_path: Path, *, lang: str = "ch") -> OCRResult:
        ...
```

建议 provider：

1. `mock`：当前演示兜底，永远可用。
2. `rapidocr`：第一阶段本地真实 OCR。
3. `paddleocr`：高质量可选 OCR。
4. `tesseract`：系统命令兜底，可用于 LoongArch/Kylin 现场解释。

## 4. 配置建议

新增配置应默认不启用重依赖：

```env
OCR_PROVIDER=mock
OCR_LANG=ch
OCR_MAX_PAGES=3
OCR_ENABLE_FOR_PDF=auto
```

可选依赖单独放入新文件：

```text
backend/requirements-ocr.txt
```

不要把 OCR 依赖加入 `backend/requirements.txt`。当前主 requirements 必须继续保持 LoongArch/Kylin 最小可运行链路。

## 5. 验证策略

第一轮只做 3 个样本：

1. 一张现场故障图片，包含故障码或铭牌文字。
2. 一页扫描版中文维修手册截图。
3. 官方 PDF 中截取的一页图片型样本。

验收标准：

1. OCR 能返回中文文本，且非空。
2. 生成的 OCR chunk 能被 `/api/search` 命中。
3. `/api/rag/answer` citations 能引用 OCR 来源。
4. OCR 失败时返回 `fallback=true` 或资料状态保持 `needs_ocr`，不能影响已有文本检索、RAG、案例审核闭环。
5. 文档中明确记录 Windows、Docker、LoongArch/Kylin 三类环境的安装结果。

## 6. 许可证与来源

1. PaddleOCR：Apache-2.0；官方仓库说明其支持 PP-OCRv5、PP-StructureV3、PaddleOCR-VL 等能力。
2. RapidOCR：Apache-2.0；官方仓库说明其基于 ONNX Runtime、OpenVINO、MNN、PaddlePaddle、TensorRT、PyTorch 等多推理后端。
3. Docling：MIT；官方仓库说明支持 PDF、Office、图片、OCR、Markdown/JSON 导出和本地执行。
4. MinerU：基于 Apache-2.0 的自定义 MinerU Open Source License；官方仓库说明其可将 PDF、Office、图片、网页转换为 Markdown/JSON，并自动处理扫描 PDF/OCR。
5. Tesseract：Apache-2.0；适合作为系统包层面的兜底 OCR。

## 7. 建议下一步

1. 新增 `backend/app/ocr_adapter.py`，先实现 `mock` 和 `rapidocr` 两个 provider。
2. 新增 `backend/requirements-ocr.txt`，只放可选 OCR 依赖。
3. 在 `analyze_knowledge_document()` 中加入 OCR 分支：图片和 `needs_ocr` PDF 可走 OCR 后生成 chunks。
4. 新增测试：OCR provider 缺失时自动 fallback；mock OCR 生成 chunk；OCR chunk 可被检索命中。
5. 在 `current-handoff.md` 和 `agent-startup-context.md` 中记录 OCR 是“可选增强”，不是默认生产级视觉诊断。
