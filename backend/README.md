# Backend

FastAPI service for the MVP demo. It reads seed data from `data/examples/` and exposes the API contract under `/api`.

## Local Run

```powershell
cd ..
.\scripts\setup-anaconda.ps1
.\scripts\start-backend.ps1
```

The backend now uses Anaconda's Python to create and manage the project-local `.venv` under `backend/`.

Health check:

```text
GET http://127.0.0.1:8000/api/health
```
