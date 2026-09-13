# ADR 0023 — Tercer adaptador de LLM: Anthropic Claude

**Estado:** Aceptada · 2026-09-13

## Contexto

[ADR 0022](0022-adaptador-openai-sin-tocar-el-orquestador.md) ya dejó el
patrón resuelto: un adaptador que implementa la superficie mínima que
`orchestrator.py` usa de `google.genai.Client`
(`.models.generate_content(model=, contents=, config=)`), sin tocar el
tool-loop ni sus ~250 tests. Esa misma ADR terminaba anticipando esto:
"Agregar un tercer proveedor real (ej. Anthropic) significa un adaptador más
con la misma forma, no una reescritura."

Además de la redundancia frente a cuota agotada (el motivo original de
tener OpenAI como segundo proveedor), un análisis de la competencia del
reto mostró que un equipo rival justifica su elección de LLM con **6
perfiles de despliegue** distintos (Gemini, Anthropic, dos variantes de
CLI, modo híbrido y offline). Tener Gemini + OpenAI ya cerraba la brecha de
"un solo proveedor gratuito sin respaldo de pago"; agregar Anthropic Claude
además demuestra que la arquitectura de adaptadores realmente escala a un
tercer proveedor sin fricción, no solo a dos.

## Decisión

`anthropic_compat_client.py` expone `AnthropicCompatClient`, con exactamente
la misma forma que `OpenAICompatClient`, pero llamando a la Messages API de
Anthropic (`client.messages.create(model=, max_tokens=, system=, tools=,
messages=)`).

La traducción de tool calls tiene una diferencia real frente a OpenAI, no
solo cosmética: Anthropic exige que cada bloque `tool_result.tool_use_id`
coincida *exactamente* con el `id` de un bloque `tool_use` presente antes en
la misma request — a diferencia de OpenAI, que solo pide que el
`tool_call_id` sea único dentro de la conversación. Pero `contents` (la
lista genérica de `types.Content`/`Part` que usa el orquestador) no tiene
dónde guardar el id real que Anthropic asignó la vez anterior —
`Part.from_function_call` no tiene ese campo. La solución es la misma que ya
usa el adaptador de OpenAI para el problema análogo (Gemini no trae ids):
nunca depender del id real devuelto por el proveedor, sino regenerar ids
sintéticos consistentes *dentro de cada traducción* de `contents` a mensajes
de Anthropic — mismo orden posicional para el `tool_use` y su `tool_result`
correspondiente. Anthropic solo valida consistencia dentro de una misma
request, así que esto satisface la API sin necesitar memoria de ids reales
entre llamadas.

Otra diferencia real: Anthropic agrupa todos los `tool_result` de una ronda
en **un solo** mensaje `user` con varios bloques, mientras que OpenAI usa un
mensaje `role: "tool"` separado por cada llamada. El adaptador acumula los
`Part` de function_response consecutivos y los vacía en un solo mensaje
apenas aparece cualquier otra cosa (texto, o el siguiente turno del
asistente).

`LLM_PROVIDER` gana un cuarto valor: `gemini` (default) | `openai` |
`anthropic` | `fake`. Modelo default cuando `ANTHROPIC_MODEL` no está
seteado: `claude-opus-5`.

## Consecuencias

- Mismas limitaciones deliberadas que el adaptador de OpenAI: una llamada de
  tool-calling por ronda, sin streaming, sin contenido multimodal — no es un
  SDK genérico de Anthropic, es angosto a propósito.
- Se reutiliza `_schema_to_json_schema` de `openai_compat_client.py` tal
  cual: el `input_schema` que espera Anthropic es JSON Schema plano, el
  mismo formato que ya usa `parameters` en OpenAI — no hay conversión nueva
  que escribir ahí.
- Nadie corrió pruebas de calidad de respuesta lado a lado entre los tres
  proveedores; solo se verificó que el flujo mecánico (tool calling
  multi-ronda a través del `Orchestrator` real, function responses, parseo
  A2UI) funciona igual con los tres.
- Con tres adaptadores reales confirmando la misma forma, el patrón de ADR
  0022 queda validado como genuinamente extensible, no como una solución ad
  hoc para un segundo proveedor.
