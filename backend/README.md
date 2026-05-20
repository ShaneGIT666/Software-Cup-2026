# Backend

FastAPI service for the MVP demo. It reads seed data from `data/examples/` and exposes the API contract under `/api`.

## Local Run

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If `python` is not available on Windows, install Python 3.10+ or run the project-level helper script from the repository root:

```powershell
.\scripts\start-backend.ps1
```

Health check:

```text
GET http://127.0.0.1:8000/api/health
```
