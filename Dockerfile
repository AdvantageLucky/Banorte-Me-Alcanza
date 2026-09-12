# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock ./
COPY src ./src

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:${PATH}"

RUN mkdir -p /data
VOLUME /data

EXPOSE 10000

# CMD invoca el script ya instalado en el venv directamente (no "uv run"):
# "uv run" re-sincroniza el proyecto en cada arranque -incluyendo el grupo
# dev (pytest, etc.)-, lo cual es lento y requiere red en cada restart del
# contenedor. El venv ya quedó completo en el build de arriba.
CMD ["me-alcanza"]
