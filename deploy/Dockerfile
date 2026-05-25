# syntax=docker/dockerfile:1.7
# Container image for the LangGraph FastAPI backend.
# Build context: repo root (not deploy/), so paths are backend/...

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install deps in their own layer so code changes don't bust the wheel cache.
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# App code only — tests, venv, frontend, eval, deploy/ etc. stay out via .dockerignore.
COPY backend/app /app/app

# Non-root user. Cloud Run doesn't require it but the image is cleaner.
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin runner \
 && chown -R runner:runner /app
USER runner

# Cloud Run injects PORT at runtime (default 8080). The CMD must honour it.
ENV PORT=8080
EXPOSE 8080

# sh -c so ${PORT} expands at container start.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
