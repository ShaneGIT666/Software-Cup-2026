# Frontend

> 本文件只维护前端开发入口与稳定接入边界。[根 README](../README.md)是文档入口，产品范围和验收语义只以 [SRS](../docs/requirements/software-requirements-spec.md) 为准，当前实现状态、证据和缺口只以[现行需求追踪矩阵](../docs/requirements/current-traceability-matrix.md)为准。

## 迁移期前端资产边界

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
- 客户端统一解析 v1 错误信封和 request ID。当前 15 个 v1 operation 已在进程内覆盖显式/未捕获 5xx、请求校验、日志失败关闭、具体 success/page item DTO 和封闭错误 schema；该证据可作为 OpenAPI 生成输入，但不代表生成器、生成产物或真实浏览器消费已经验收。新增 operation 前必须先完成统一方案 R1 的动态公共门禁改造，并继续提供具体模型及所属模块的精确映射测试。
- 后端已在进程内验证 CORS 暴露 `ETag`；真实跨域浏览器读取并以 `If-Match` 回传仍待 E2E 验收。

M6 的最新状态只在[现行追踪矩阵](../docs/requirements/current-traceability-matrix.md)维护；客户端契约和接入顺序只参考统一方案的 [v1 HTTP 契约](../docs/design/follow-up-development-plan.md#v1-http-contract)与[后续开发路线](../docs/design/follow-up-development-plan.md#remaining-roadmap)。
