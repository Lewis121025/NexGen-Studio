# Lewis AI System - Production Dockerfile
FROM python:3.11-slim AS base

LABEL maintainer="Lewis Engineering <engineering@example.com>"
LABEL description="Lewis AI System - Video creation and ReAct tasking platform"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY docs ./docs
COPY docker ./docker

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir .

RUN useradd -m -u 1000 lewis && \
    chown -R lewis:lewis /app && \
    chmod +x /app/docker/entrypoint.sh

USER lewis

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["uvicorn", "nexgen_studio.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
