# Frontend

> 本文件是前端开发辅助说明。产品范围、状态和验收口径以[根 README](../README.md)、[SRS](../docs/requirements/software-requirements-spec.md)和[现行需求追踪矩阵](../docs/requirements/current-traceability-matrix.md)为准。

## 当前实现

当前目录是 Vue 3 + TypeScript + Vite + Element Plus 单页原型：

- `src/App.vue` 和 `src/api.ts` 仍调用迁移期旧 `/api`。
- Vite 开发代理仍转发 `/api` 和 `/uploads` 到 `http://127.0.0.1:8000`。
- 尚无 Vue Router、登录页面、权限 store、`/api/v1` 客户端或 CSRF 闭环。
- `e2e/smoke.spec.ts` 和 Playwright 配置存在，但 `@playwright/test` 尚未写入 `package.json`/lockfile，不能把 E2E 视为可复现或已通过。

这些内容只证明原型资产存在或可构建，不表示 M6 已集成。

## 本地运行

```powershell
cd frontend
npm ci
npm run dev
```

只有在修改依赖时才使用 `npm install`，并必须同时提交 `package.json` 与 `package-lock.json` 的一致变更。

## 目标前端边界

- 新生产客户端统一放入 `src/services/v1/` 并只访问 `/api/v1`；不得继续向旧 `api.ts` 增加生产功能。
- Cookie 会话请求使用 `credentials: include`；写请求按 M1/OpenAPI 契约携带 CSRF token。
- 授权身份、审核人和角色只来自服务端认证结果；前端不得发送 `reviewer`、`actorId` 或角色字段决定授权。
- 客户端统一解析 v1 错误信封和 request ID。后端 OpenAPI 已为全部 v1 操作声明通用 `500/V1Response` 错误结构并通过契约测试，该证据只支持公共错误基类；它不证明显式 `HTTPException`/`AppError` 5xx 或服务端日志已完整脱敏。现有成功响应的 `data/items` 仍可为 `Any`，不得据此生成或锁定最终业务客户端；真实浏览器接入仍须在 M6/D4 验证。
- 后端已在进程内验证 CORS 暴露 `ETag`；真实跨域浏览器读取并以 `If-Match` 回传仍待 E2E 验收。

M6 的最新状态只在[现行追踪矩阵](../docs/requirements/current-traceability-matrix.md)维护；接入门槛和顺序参考[模块进度计划](../docs/design/module-build-progress-and-interface-plan.md)。
