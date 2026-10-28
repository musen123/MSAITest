FROM ghcr.io/astral-sh/uv:0.10.10 AS uvbin
FROM python:3.13-slim AS builder
COPY --from=uvbin /uv /uvx /usr/local/bin/
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
RUN apt-get update && apt-get install -y --no-install-recommends build-essential default-libmysqlclient-dev pkg-config && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.13-slim
COPY --from=uvbin /uv /uvx /usr/local/bin/
RUN apt-get update && apt-get install -y --no-install-recommends libmariadb3 libgomp1 fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_PYTHON_DOWNLOADS=never
COPY --from=builder /app/.venv /app/.venv
COPY . .
RUN useradd --create-home appuser && mkdir -p /app/data /app/archives && chown -R appuser:appuser /app
USER appuser
EXPOSE 8888
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8888"]
