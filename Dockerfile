FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY schemas ./schemas

RUN pip install --no-cache-dir .

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD curl -f http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "context_engine.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
