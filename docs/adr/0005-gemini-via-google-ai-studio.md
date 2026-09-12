# ADR 0005 — Gemini a través de Google AI Studio (API gratuita)

**Estado:** Aceptada · 2026-09-11

## Contexto

El LLM debe interpretar la intención, decidir qué tools llamar y emitir bloques
A2UI válidos con el formato `DirectJsonFormat` del SDK. El presupuesto del
equipo para inferencia es cero. Se necesitaba function calling estable y una
ventana de contexto suficiente para el catálogo A2UI completo con schema.

## Decisión

Usar Gemini vía Google AI Studio con la cuota gratuita. El modelo concreto es un
valor de entorno (`GEMINI_MODEL`) y no una constante: el día del evento los
modelos `*-flash` gratuitos devolvieron `503` por saturación y hubo que cambiar
sin redeploy. El proveedor también es un flag (`LLM_PROVIDER=gemini|fake`,
[ADR 0016](0016-modo-offline-determinista.md)).

## Consecuencias

- Costo cero y el SDK A2UI de Python trae ejemplos y formato pensados para
  Gemini.
- La cuota gratuita es el mayor riesgo de la demo: por eso existe el modo
  offline y por eso el modelo es configurable.
- El orquestador está escrito contra `google-genai` (tipos `Content`, `Part`,
  `FunctionResponse`); cambiar de proveedor no es trivial. Se aceptó a cambio de
  velocidad.
