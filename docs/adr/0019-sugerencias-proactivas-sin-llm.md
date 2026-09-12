# ADR 0019 — Sugerencias proactivas deterministas, fuera del chat

**Estado:** Aceptada · 2026-09-12

## Contexto

La pestaña *Dashboard* era un placeholder. Se quería que la app avisara sola
de situaciones de riesgo (saldo que se proyecta negativo, gasto fijo grande a
días de vencer, meta que no se va a cumplir) sin que el usuario pregunte. Meter
al LLM en ese camino añadía latencia, costo de cuota y el riesgo de que el
modelo "narrara" una alerta que no existe.

## Decisión

Tres reglas puras en `sugerencias_engine.py` con umbrales como constantes
(≤ 5 días y ≥ 30 % del saldo para gastos; ≤ 30 días sin completar para metas;
`simular_flujo_de_caja` con objetivo 0 hasta cada ingreso para liquidez). Se
generan bajo demanda en cada `GET /api/sugerencias`, se persisten en la tabla
`sugerencias` con deduplicación por `tipo + entidad_id` mientras haya una
pendiente, y tienen historial (`pendiente | atendida | descartada`). Las tools
correspondientes no se exponen al LLM.

## Consecuencias

- Alertas instantáneas, testeables y sin cuota.
- No es UI generativa: es un feed clásico. No suma en los rubros de LLM/A2UI del
  reto; suma en utilidad percibida.
- Con el seed actual solo dispara `gasto_fijo_proximo` (la meta está a 32 días,
  el umbral es 30; la nómina llega antes que los gastos). Para la demo hay que
  ajustar seed o umbral, o no mostrar el Dashboard.
- Sin cron: si nadie abre el Dashboard, no se generan.
