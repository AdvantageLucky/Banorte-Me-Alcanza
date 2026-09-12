# ADR 0004 — Backend en Python 3.14 con FastAPI y uv

**Estado:** Aceptada · 2026-09-11

## Contexto

El stack es libre. El equipo tenía que producir en dos días un servidor MCP, un
orquestador con function calling y una capa A2UI, y quería tests desde el primer
commit. Los SDKs oficiales de las tres piezas obligatorias tienen implementación
de primera clase en Python: `mcp` (servidor y cliente), `google-genai` y
`a2ui-agent-sdk` (catálogo básico y generador de prompt).

## Decisión

Python 3.14 con FastAPI + uvicorn para la API, `uv` para dependencias con
lockfile reproducible, pytest con `asyncio_mode = "auto"`. Un solo `pyproject`
contiene backend y servidor MCP como paquetes hermanos (`me_alcanza.backend`,
`me_alcanza.mcp_bank`).

## Consecuencias

- Los tres SDKs se usan sin adaptadores; el prompt A2UI lo genera la librería
  oficial y no una copia a mano.
- La imagen Docker parte de `ghcr.io/astral-sh/uv:python3.14-bookworm-slim` y
  hace `uv sync --frozen`; el arranque del contenedor no toca la red.
- Python 3.14 es reciente: algunas dependencias emiten `DeprecationWarning`
  (`google-genai`, `starlette`). Se aceptan.
