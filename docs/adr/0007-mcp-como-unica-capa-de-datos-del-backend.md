# ADR 0007 — El backend habla con los datos solo a través del MCP, incluso fuera del LLM

**Estado:** Aceptada · 2026-09-12

## Contexto

Muchas rutas REST no involucran al LLM: las pestañas *Yo* y *Dashboard* hacen
CRUD de contactos, gastos, metas; el historial de conversaciones se guarda y se
lee; las sugerencias se generan. El backend importa el mismo paquete que el
servidor MCP, así que podría llamar a `db.py` directamente y saltarse el MCP en
esos caminos. La pregunta explícita fue: *¿por qué el servidor consume el MCP
también para cosas que no son "de MCP"?*

## Decisión

El backend **nunca** importa `db.py` ni abre la base de datos. Toda lectura y
toda mutación — venga del LLM, de una ruta REST o del propio orquestador
guardando historial — pasa por una tool del servidor `core-bancario`. Las tools
que el LLM no debe ver se registran igual en el servidor pero no se declaran en
el catálogo del modelo ([ADR 0008](0008-superficie-de-tools-segmentada.md)).

## Consecuencias

- Una sola frontera de datos: el backend es un BFF sin estado que orquesta; el
  MCP es el "core bancario". Si mañana el core es real, el backend no cambia.
- Toda regla de negocio (saldo insuficiente, meta con apartados activos, estado
  inválido) vive en un solo lugar y llega al cliente como `400` con el mensaje
  original, sin importar el camino.
- Cuesta una llamada IPC por operación y el servidor MCP acumula tools que no son
  "para el agente" (35 en total). Se acepta: la alternativa era dos capas de
  acceso a datos que divergen.
