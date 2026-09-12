# ADR 0002 — Un solo problema: "¿me alcanza para X?"

**Estado:** Aceptada · 2026-09-11

## Contexto

El reto deja el caso de uso libre dentro de servicios financieros y aconseja
"elegir un problema pequeño y resolverlo completo: un solo flujo con una UI que
de verdad cambia y una acción que de verdad ocurre vale más que cinco pantallas a
medias". El 45 % de la evaluación es utilidad + calidad de la UI generada; el
30 % es la ingeniería del ciclo LLM → MCP → A2UI → acción.

## Decisión

El producto responde una sola pregunta — *¿me alcanza el dinero para un gasto
futuro?* — y cierra con una acción real: si no alcanza, propone un apartado de
ahorro que el usuario activa con un toque y que descuenta saldo de verdad. Todo
lo demás (transferencias, alta de contactos/gastos/metas por chat, pestañas de
consulta, sugerencias, score) existe para dar contexto a esa pregunta o para que
la demo no se sienta vacía; ninguno es el flujo principal.

## Consecuencias

- El system prompt, el seed de datos y la demo están optimizados para que la
  cuenta `ana` dispare exactamente ese flujo el día que sea.
- Se rechazaron ideas con más "wow" pero sin acción cerrada (inversiones,
  crédito, seguros).
- El riesgo es parecer pequeño frente a equipos con más pantallas; se acepta
  porque el brief penaliza explícitamente lo incompleto.
