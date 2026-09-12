# ADR 0006 — Servidor MCP como proceso separado sobre stdio

**Estado:** Aceptada · 2026-09-11

## Contexto

MCP es pieza obligatoria del reto. Las opciones eran: (a) un "registry" de
funciones en el mismo proceso del backend etiquetado como MCP, (b) un servidor
MCP sobre HTTP/SSE en otro contenedor, (c) un servidor MCP real lanzado como
subproceso y hablado por stdio con el SDK oficial.

## Decisión

Opción (c). `app.py` levanta `python -m me_alcanza.mcp_bank.server` en el
`lifespan` de FastAPI y mantiene una `ClientSession` viva durante toda la vida
del proceso ([`mcp_client.py`](../../src/me_alcanza/backend/mcp_client.py)). El
servidor se llama `core-bancario` y simula el sistema central del banco: es el
único que toca la base de datos.

## Consecuencias

- Es MCP de verdad: cualquier cliente MCP (Claude Desktop, un inspector) puede
  conectarse al mismo servidor sin el backend.
- No hay un puerto ni un contenedor extra que operar; en Docker el backend y el
  MCP viajan en la misma imagen.
- Latencia de IPC por llamada y una sola sesión compartida por todas las
  requests. Suficiente para la demo; en producción sería HTTP con pool.
- Los tests de `tests/mcp_bank/test_server.py` levantan el servidor real por
  stdio contra una DB temporal — el contrato se prueba, no se mockea.
