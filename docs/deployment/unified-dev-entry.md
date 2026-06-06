# 统一开发入口说明

更新时间：2026-06-06

用途：让开发者和 Coding Agent 在没有会话上下文的情况下，用同一个入口启动、停止、检查和排查本地前后端服务。

## 1. 推荐命令

在仓库根目录运行：

```bat
dev start
dev status
dev verify
dev logs
dev stop
dev restart
```

默认访问地址：

```text
前端：http://127.0.0.1:5173/
后端：http://127.0.0.1:8000/api/health
```

## 2. 命令含义

1. `dev start`：后台启动 FastAPI 后端和 Vite 前端。
2. `dev status`：查看保存的 PID、进程状态、端口和 URL。
3. `dev verify`：请求后端 `/api/health`，并检查前端首页是否可访问。
4. `dev logs`：查看最近的后端与前端日志。
5. `dev stop`：停止保存的进程，并尝试清理 8000/5173 端口上的残留服务。
6. `dev restart`：先停止再启动，适合改动环境变量或依赖后使用。

## 3. PowerShell 入口

如果不使用 `dev.bat`，可以直接调用：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Action start -OpenBrowser
```

可选动作：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Action status
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Action verify
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Action logs
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Action stop
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Action restart
```

## 4. 兼容入口

以下旧入口仍可使用，但只是兼容包装：

```bat
start-dev.bat
stop-dev.bat
```

它们内部已经转发到 `scripts/dev.ps1`，后续文档和演示优先使用 `dev.bat`。

## 5. 日志与状态文件

默认运行状态目录：

```text
.dev-runtime/
```

如果 `.dev-runtime` 因历史权限、沙箱或受控目录策略不可写，脚本会自动降级到系统临时目录：

```text
%TEMP%\software-cup-2026-dev-runtime\
```

常见日志文件：

```text
backend.log
backend.err.log
frontend.log
frontend.err.log
dev-services.json
```

## 6. 已处理的启动稳定性问题

1. PowerShell 5 在重定向原生命令 stderr 时，可能把 Uvicorn/Vite 的普通日志包装成 `NativeCommandError`。当前启动脚本在进入长期服务命令前已放宽错误偏好，避免正常日志导致服务退出。
2. Vite 默认配置加载可能写入 `frontend/node_modules/.vite-temp`，在部分受限环境会触发 `EPERM`。当前前端启动已使用 `--configLoader runner`，避免依赖该临时目录写权限。
3. `scripts/dev.ps1` 会生成 wrapper 脚本启动后端和前端，使参数、日志和 PID 管理更稳定。

## 7. 验证记录

本地验证命令：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Action start
Start-Sleep -Seconds 30
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Action verify
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Action stop
```

验证结果：

```text
Backend OK: http://127.0.0.1:8000/api/health
Frontend OK: http://127.0.0.1:5173/
Development services stopped.
```

## 8. 故障排查

1. 如果 `dev verify` 后端失败，先运行 `dev logs` 查看 `backend.err.log`，再确认 `backend/.venv/Scripts/python.exe` 是否存在。
2. 如果前端失败，先运行 `dev logs` 查看 Vite 输出，再确认 `frontend/node_modules/` 是否存在。
3. 如果端口占用，运行 `dev stop`；仍无法释放时，用 `dev status` 和系统任务管理器确认残留进程。
4. 如果网络或真实 API 不稳定，设置 `REMOTE_API_MODE=off`，系统会使用本地检索和 mock 兜底链路。
