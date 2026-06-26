# syntax=docker/dockerfile:1

# Keep BASE_IMAGE configurable because LoongArch image availability differs
# across Kylin/Loongnix/Docker Hub environments.
ARG BASE_IMAGE=cr.loongnix.cn/library/python:3.11
FROM ${BASE_IMAGE}
ARG INSTALL_CHROMA=false
ARG INSTALL_TESSERACT=false

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
    OCR_PROVIDER=mock \
    RAG_VECTOR_STORE=sqlite \
    RAG_VECTOR_SQLITE_ENGINE=python_scan \
    RAG_VECTOR_ENHANCER=off \
    RAG_VECTOR_FALLBACK_LOCAL=on

WORKDIR /app

RUN if [ "${INSTALL_TESSERACT}" = "true" ]; then \
        apt-get update \
        && apt-get install -y --no-install-recommends tesseract-ocr \
        && rm -rf /var/lib/apt/lists/*; \
    fi

COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && INSTALL_CHROMA=${INSTALL_CHROMA} python -c "import os; from pathlib import Path; p=Path('/app/backend/requirements.txt'); q=Path('/app/backend/requirements-container.txt'); lines=p.read_text(encoding='utf-8').splitlines(); install_chroma=os.environ.get('INSTALL_CHROMA','false').lower() in {'1','true','yes'}; lines.extend(['chromadb>=0.5.0,<2.0.0'] if install_chroma else []); q.write_text('\n'.join(lines) + '\n', encoding='utf-8')" \
    && python -m pip install --no-cache-dir -r /app/backend/requirements-container.txt

COPY backend /app/backend
COPY data/examples /app/data/examples
COPY frontend/dist /app/frontend/dist
COPY .env.example README.md /app/

RUN mkdir -p /app/runtime/knowledge /app/runtime/uploads

EXPOSE 8000

CMD ["python", "-c", "import uvicorn.server; uvicorn.server.HANDLED_SIGNALS=(); import uvicorn; uvicorn.run('backend.app.main:app', host='0.0.0.0', port=8000)"]
