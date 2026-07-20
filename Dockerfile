FROM ghcr.io/astral-sh/uv:0.11.29 AS uv

FROM python:3.12-slim-bookworm

COPY --from=uv /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY agents ./agents
COPY app ./app
COPY graph ./graph
COPY tools ./tools

EXPOSE 5000

CMD ["uv", "run", "--no-sync", "python", "-m", "app.start"]
