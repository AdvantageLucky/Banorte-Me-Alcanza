# Diseño: Explicabilidad ("¿cómo se calculó?") + Score de salud financiera

## Objetivo

Dos features de confianza/transparencia: (A) cada tarjeta A2UI con un número
calculado o derivado (saldo proyectado, margen de flujo de caja, etc.) trae
un botón que abre un panel explicando cómo se llegó a ese número; (B) un
score 0-100 de salud financiera de la cuenta, calculado con reglas
deterministas (reusa la detección de la spec de sugerencias proactivas).

**Depende de**: `docs/superpowers/plans/2026-09-12-sugerencias-proactivas.md`
ya mergeado — el score reusa `sugerencias_engine.detectar_*` directamente.
Ejecutar este plan solo después de ese.

## Parte A — Explicabilidad ("¿Cómo se calculó?")

**Hallazgo clave que simplifica todo esto:** el catálogo básico de A2UI ya
trae un componente `Modal` (`trigger`: id de un componente que lo abre,
`content`: id del componente a mostrar dentro) — es 100% client-side, sin
round-trip al servidor, y **ya está soportado por los renderers estándar**
que usan React y Flutter (`@a2ui/react basicCatalog`, `BasicCatalogItems`).
No requiere ni una línea de código nuevo de frontend.

**Cambio, 100% backend:**
- Agregar `"Modal"` a `_ALLOWED_COMPONENTS` en `orchestrator.py`.
- Agregar una instrucción a `ui_description` (dentro de `build_system_prompt`):
  para cualquier tarjeta que muestre un número calculado o derivado (saldo
  proyectado, margen de `simular_flujo_de_caja`, desglose de una
  transferencia, etc.), agregar un `Button` `variant='borderless'` con texto
  "¿Cómo se calculó?" cuyo `trigger` abra un `Modal` cuyo `content` sea una
  `Column` con el desglose (los montos/fechas que entraron al cálculo).

Sin endpoints nuevos, sin DTOs nuevos — es puro prompt engineering + una
constante.

## Parte B — Score de salud financiera

Reusa las 3 funciones de detección ya construidas en el sub-proyecto de
sugerencias (`detectar_riesgo_liquidez`, `detectar_gastos_fijos_proximos`,
`detectar_metas_en_riesgo`) para computar un score determinista 0-100, sin
LLM:

```
score = 100
  - 30 si hay riesgo de liquidez detectado
  - min(5 * num_gastos_fijos_proximos, 20)
  - min(10 * num_metas_en_riesgo, 20)
  + 10 si hay al menos un apartado activo
clamp(0, 100)

categoria: >=80 "Saludable" | >=50 "Atención" | <50 "Riesgo"
```

Los pesos son arbitrarios, elegidos para que el score se sienta razonable
con los datos de demo — no hay ciencia actuarial detrás, es una demo.

**Nueva tool MCP** `calcular_score_salud_financiera(account_id) -> dict` con
forma `{"score": int, "categoria": str, "factores": list[str]}` (`factores`
es una lista de frases en español explicando qué subió/bajó el score — la
"explicabilidad" del score mismo).

**Nuevo endpoint REST** `GET /api/score-salud-financiera`.

## Fuera de alcance

El score no se expone al LLM (mismo criterio que las sugerencias: es un dato
determinista consumido directo por el frontend, no conversacional). No hay
persistencia de histórico de scores (se calcula al vuelo cada vez que se
pide) — un histórico de "tu score a través del tiempo" seria una iteración
futura interesante pero no es parte de este spec.

## Testing

Tests de la función pura de score (`sugerencias_engine.py`, con distintas
combinaciones de candidatos), tests de la tool MCP nueva, tests del endpoint
REST. La Parte A (Modal) se verifica con un test que confirma que `"Modal"`
está en `_ALLOWED_COMPONENTS` y que el texto de `ui_description` menciona la
instrucción — no hay forma de testear automáticamente que el LLM realmente
lo use bien sin gastar cuota real de Gemini; eso se verifica manualmente.
