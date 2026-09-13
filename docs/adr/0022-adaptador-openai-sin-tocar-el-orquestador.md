# ADR 0022 — Soporte multi-proveedor de LLM vía adaptador, sin reescribir el orquestador

**Estado:** Aceptada · 2026-09-12

## Contexto

[ADR 0005](0005-gemini-via-google-ai-studio.md) ya advertía el riesgo: "el
orquestador está escrito contra `google-genai` (tipos `Content`, `Part`,
`FunctionResponse`); cambiar de proveedor no es trivial." Ese riesgo se
materializó dos veces el mismo día del evento — cuota de Gemini agotada a
media demo — y el equipo consiguió acceso a la API de OpenAI como segunda
opción real. Depender de un solo proveedor gratuito, sin alternativa de pago
de respaldo, era el punto de falla más frágil de todo el proyecto.

La opción obvia — generalizar `orchestrator.py` con una interfaz propia de
"proveedor de LLM" (mensajes, tools y respuestas en un formato neutral) —
significa reescribir el tool-loop, la persistencia de conversación
([ADR 0015](0015-memoria-de-conversacion-por-hilos.md)) y el fallback
offline ([ADR 0016](0016-modo-offline-determinista.md)), todo blindado ese
mismo día con varias rondas de fixes tras encontrar bugs reales (una
respuesta exitosa que se descartaba por un fallo de persistencia, historial
sin límite agotando cuota dentro de una sola conversación). Reescribir esa
lógica multiplicaba el riesgo exactamente donde ya se había invertido en
hacerla confiable, y hubiera obligado a reescribir los ~250 tests que la
cubren.

## Decisión

No tocar `orchestrator.py`. En su lugar, `openai_compat_client.py` expone un
`OpenAICompatClient` que implementa la única superficie que el orquestador
realmente usa de `google.genai.Client` — `.models.generate_content(model=,
contents=, config=) -> response` con `.function_calls`, `.candidates[0].content`
y `.text` — pero por dentro llama a la API de OpenAI (Chat Completions +
tool calling). `google.genai.types.Content`/`Part` se usan como lo que
realmente son: contenedores de datos sin conexión a red propia, no algo
atado a Gemini, así que el adaptador los construye y los lee sin necesitar
una cuenta ni una llamada real a Gemini.

El punto delicado es la correlación de tool calls: OpenAI exige un
`tool_call_id` único por llamada, pero Gemini no tiene ese concepto — el
código existente correlaciona por posición dentro del turno, no por nombre,
porque el prompt del sistema pide explícitamente llamar la misma tool varias
veces en un turno (`proponer_transferencia` una vez por contacto ambiguo).
El adaptador asigna ids sintéticos por posición (una cola FIFO) en vez de
usar el nombre de la tool, precisamente para no romper ese caso.

`LLM_PROVIDER` gana un tercer valor: `gemini` (default) | `openai` | `fake`
([ADR 0016](0016-modo-offline-determinista.md)). `main.py` decide qué
cliente construir según ese flag; `create_app`/`Orchestrator` no saben ni
les importa cuál es — reciben cualquier objeto con la forma correcta.

## Consecuencias

- Cero cambios a `orchestrator.py`, `db.py`, `server.py` o sus tests: el
  tool-loop, la memoria de conversación y el fallback offline siguen siendo
  exactamente el código ya probado.
- El adaptador solo soporta lo que el orquestador realmente usa (una llamada
  de tool-calling por ronda, sin streaming, sin contenido multimodal) — no es
  un SDK de OpenAI genérico, es deliberadamente angosto.
- Cambiar de proveedor sigue sin ser "gratis" en el sentido de que cada
  modelo tiene su propio criterio para llamar tools y su propio estilo de
  respuesta — el mismo prompt puede comportarse distinto en Gemini que en
  GPT. Nadie corrió pruebas de calidad de respuesta lado a lado; solo se
  verificó que el flujo mecánico (tool calling multi-ronda a través del
  `Orchestrator` real, function responses, parseo A2UI) funciona igual con
  ambos.
- Hay dos puntos de llamada a `generate_content`: el tool-loop del chat
  (con `tools`) y `generar_propuesta_sugerencia` para el tab "Atención"
  (sin `tools`). El primer borrador del adaptador serializaba `tools=None`
  literalmente, lo que rompía el segundo con un 400 de la API de OpenAI;
  se corrigió omitiendo la clave `tools` cuando no hay tools que declarar.
- Agregar un tercer proveedor real (ej. Anthropic) significa un adaptador
  más con la misma forma, no una reescritura — el costo ya se pagó una vez.
