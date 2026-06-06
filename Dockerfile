# syntax=docker/dockerfile:1

# Keep BASE_IMAGE configurable because LoongArch image availability differs
# across Kylin/Loongnix/Docker Hub environments.
ARG BASE_IMAGE=cr.loongnix.cn/library/python:3.11
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    APP_PORT=8000 \
    SERVE_FRONTEND=auto \
    FRONTEND_DIST_DIR=/app/frontend/dist \
    APP_EXAMPLES_DIR=/app/data/examples \
    APP_KNOWLEDGE_DIR=/app/runtime/knowledge \
    APP_UPLOAD_DIR=/app/runtime/uploads \
    REMOTE_API_MODE=off \
    LLM_PROVIDER=mock \
    MULTIMODAL_PROVIDER=mock \
    RAG_VECTOR_STORE=off

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY data/examples /app/data/examples
COPY frontend/dist /app/frontend/dist
COPY .env.example README.md /app/

RUN mkdir -p /app/runtime/knowledge /app/runtime/uploads

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
