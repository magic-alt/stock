FROM python:3.12-slim AS base

LABEL maintainer="Unified Quant Platform"
LABEL version="5.0"

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Install core Python deps first (caching layer)
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir ".[api,perf]"

# ---------------------------------------------------------------------------
# Data layer: + DuckDB + Parquet tools
# ---------------------------------------------------------------------------
FROM base AS data
RUN pip install --no-cache-dir duckdb polars pyarrow

# ---------------------------------------------------------------------------
# Full image: + ML deps (optional, large)
# ---------------------------------------------------------------------------
FROM data AS full
RUN pip install --no-cache-dir ".[ml]" || echo "ML deps skipped (optional)"

# ---------------------------------------------------------------------------
# Production image: minimal
# ---------------------------------------------------------------------------
FROM data AS production

COPY src/ ./src/
COPY scripts/ ./scripts/
COPY config.yaml.example ./config.yaml.example

# Create runtime directories
RUN mkdir -p cache report data_lake logs

# Non-root user for security
RUN useradd -m -r quantuser && chown -R quantuser:quantuser /app
USER quantuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v2/health || exit 1

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "uvicorn", "src.platform.api_v2:app", "--host", "0.0.0.0", "--port", "8000"]
