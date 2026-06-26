# PPT 素材：多模态诊断页

## 设计原则

现场图片是诊断线索，不是未经审核的正式证据。

## 链路

1. 前端上传图片。
2. OCR 提取文字线索。
3. 多模态 Provider 提取视觉线索。
4. 失败时降级到 OCR/文本 LLM/标准模板。
5. 线索扩展 query context。
6. RAG 仍只引用 approved evidence。

## 亮点

- 图片诊断不阻塞主检索。
- provider/fallback 状态可见。
- 符合生产场景的知识审核边界。
