FROM python:3.12-slim AS base

LABEL maintainer="Unified Quant Platform"
LABEL version="5.0.0"

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Install core Python deps first (caching layer)
COPY requirements.txt requirements-mlops.txt pyproject.toml README.md ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt fastapi "uvicorn[standard]" duckdb polars pyarrow

# ---------------------------------------------------------------------------
# Data layer: reserved stage for cacheable data-tooling customizations
# ---------------------------------------------------------------------------
FROM base AS data
RUN python -V

# ---------------------------------------------------------------------------
# Full image: + ML deps (optional, large)
# ---------------------------------------------------------------------------
FROM data AS full
RUN pip install --no-cache-dir -r requirements-mlops.txt || echo "ML deps skipped (optional)"

# ---------------------------------------------------------------------------
# Frontend build: compile the Vue SPA for production release images
# ---------------------------------------------------------------------------
FROM node:20-alpine AS frontend-build

WORKDIR /frontend

COPY frontend/package*.json ./
COPY frontend/.npmrc ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Production image: minimal
# ---------------------------------------------------------------------------
FROM data AS production

COPY src/ ./src/
COPY scripts/ ./scripts/
COPY config.yaml.example ./config.yaml.example
COPY requirements.txt pyproject.toml README.md ./
COPY --from=frontend-build /frontend/dist ./frontend/dist

# Create runtime directories
RUN mkdir -p cache report data_lake logs

# Stable numeric UID/GID so Kubernetes runAsNonRoot can verify the image user.
RUN groupadd --gid 10001 quantuser && \
    useradd --uid 10001 --gid 10001 --create-home --no-log-init --shell /usr/sbin/nologin quantuser && \
    chown -R 10001:10001 /app
USER 10001:10001

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PLATFORM_FRONTEND_DIST=/app/frontend/dist
ENV PLATFORM_API_HOST=0.0.0.0
ENV PLATFORM_API_PORT=8000

EXPOSE 8000

# Container health means ready for traffic, not merely that the process exists.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS "http://localhost:${PLATFORM_API_PORT}/api/v2/ready" || exit 1

# The startup script and application factory both consume the same PlatformSettings object.
CMD ["python", "scripts/run_platform_api.py"]
