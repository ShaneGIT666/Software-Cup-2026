# 比赛演示运行手册

## 固定策略

1. 41 页摩托车维修手册使用赛前已经解析、逐页验证并审核通过的知识库。
2. 比赛现场只上传 1 至 3 页小样本，演示实时解析链路。
3. 不在现场重新运行整本 `full_visual`。本地实测 `smart_multimodal` 为 969.515 秒，约 16 分钟；`full_visual` 为 2460.14 秒，约 41 分钟。
4. 正式演示前确认 Renderer operational smoke、provider probe 和会话 Token 均通过。

## 演示顺序

1. 在管理中心展示 `text_fast`、`smart_multimodal`、`full_visual` 三种解析模式及适用场景。
2. 上传 1 至 3 页样本，展示页面渲染、OCR 已执行页数、OCR 提取到文字页数、OCR 空结果和真实多模态页数。
3. 打开图片知识片段，展示缩略图、手册页码、视觉类型、部件、操作与安全提示。
4. 展示新视觉知识初始为 `pending_review`，审核前 approved-only 检索无法命中。
5. 使用审核角色通过片段，再展示图文联合检索、图片缩略图和页码，以及 RAG 回答中的图片引用。
6. 明确区分机器视觉结论、审核状态和人工经验，不把未审核内容作为正式作业依据。

## 异常处置

- API 或网络异常时，`smart_multimodal` 保留正文解析结果，页面状态显示 `completed_with_warnings`。
- provider 未完成时显示读取中；请求失败后显示服务不可用；成功但无字段时显示未上报。
- OCR 空结果只计入 `ocrEmptyPages`，不冒充识别到文字，也不单独判定页面失败。
- `semanticVerified=false` 或真实多模态页数不足时显示 warning，不冒充真实图片理解。
- 现场若无法恢复 provider，改为展示赛前已审核知识库和失败保护语义，不填充假数据。
