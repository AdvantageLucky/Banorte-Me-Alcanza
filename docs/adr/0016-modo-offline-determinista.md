# ADR 0016 — Modo offline determinista como respaldo del LLM

**Estado:** Aceptada · 2026-09-12

## Contexto

El 12 de septiembre los modelos gratuitos de Gemini devolvieron `503` durante
horas. Una demo que depende de una API externa gratuita el día del evento es
una demo que puede no ocurrir. Además el backend fallaba al arrancar sin
`GOOGLE_AI_STUDIO_API_KEY`, lo que bloqueaba a quien solo quería probar el
frontend o el MCP.

## Decisión

`LLM_PROVIDER=gemini|fake`. En `fake`, un módulo puro
(`fake_provider.generar_respuesta_offline`) devuelve bloques A2UI válidos
elegidos por palabras clave del mensaje, con una tarjeta titulada "Modo
offline" que no finge ser una respuesta real. Si el proveedor es `gemini` y la
llamada lanza cualquier excepción, el orquestador cae al mismo módulo antes del
bloque de error genérico. Si no hay API key, `main.py` fuerza `fake` con un
warning en vez de abortar.

## Consecuencias

- El servidor siempre arranca; el frontend, el MCP y las pestañas de consulta se
  pueden ensayar sin cuota ni red.
- El respaldo es deliberadamente tonto (keywords, no NLP): es una red de
  seguridad, no un modelo. En la demo hay que decir explícitamente cuándo se
  está en él.
- Las respuestas offline no se guardan en el hilo
  ([ADR 0015](0015-memoria-de-conversacion-por-hilos.md)).
