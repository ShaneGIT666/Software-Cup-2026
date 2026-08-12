# Backend

FastAPI 后端正在从演示原型迁移为模块化单体。旧业务接口保留在 `/api`，用于前端与测试兼容；所有新增生产接口使用 `/api/v1`。

## 模块 0：已提供的基础能力

- `core/`：`APP_` 前缀配置、请求 ID、稳定 v1 响应与错误模型。
- `db/`：SQLAlchemy 2、PostgreSQL 连接/就绪状态与共享元数据根。
- `alembic/`：初始迁移，创建 `app_metadata` 和事务 outbox 的基础表。
- `/api/v1/health/live`：进程存活检查。
- `/api/v1/health/ready`：数据库就绪检查。生产环境设置 `APP_DATABASE_REQUIRED=true` 后，数据库未配置或不可连接时返回 `503`。

身份、知识、文件、审核、Worker 与检索业务迁移尚未开始，因此当前 `/api` 原型仍使用 JSON 存储；不要把这次数据库底座视为业务数据已经完成迁移。

## Windows 本地运行

在仓库根目录执行：

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
powershell -ExecutionPolicy Bypass -File .\scripts\init-config.ps1 -Mode offline
.\dev.bat start
```

健康检查：

```text
GET http://127.0.0.1:8000/api/health
GET http://127.0.0.1:8000/api/v1/health/live
GET http://127.0.0.1:8000/api/v1/health/ready
```

## PostgreSQL 初始化

1. 安装 PostgreSQL 16，并创建应用数据库与最小权限的应用账户。
2. 在本机 `.env` 设置连接串，示例：

   ```text
   APP_DATABASE_URL=postgresql+psycopg://repair_app:change-me@127.0.0.1:5432/repair_knowledge
   APP_DATABASE_REQUIRED=true
   ```

3. 从 `backend/` 目录执行迁移：

   ```powershell
   cd backend
   $env:APP_DATABASE_URL='postgresql+psycopg://repair_app:change-me@127.0.0.1:5432/repair_knowledge'
   .\.venv\Scripts\alembic.exe upgrade head
   ```

连接串只放在 `.env`、Windows Service 环境或企业密钥管理系统中，禁止提交到 Git。迁移先创建基础元数据和 outbox；后续领域模块会各自增加用户、文档、知识和流程表。

## 验证

```powershell
.\backend\.venv\Scripts\python.exe -m pytest tests\test_module0_foundation.py tests\test_configuration_contract.py -q
```
