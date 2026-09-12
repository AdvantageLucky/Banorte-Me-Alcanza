# ADR 0010 — El LLM decide qué mostrar; los motores deterministas deciden cuánto

**Estado:** Aceptada · 2026-09-11

## Contexto

La pregunta central requiere proyectar un saldo con ingresos y gastos futuros y
comparar contra un objetivo. Un LLM puede hacer esa aritmética la mayoría de las
veces; en banca "la mayoría de las veces" es un incidente. Además un cálculo
dentro del modelo no se puede testear.

## Decisión

Todo número derivado lo produce una función pura sin I/O, testeada con fixtures:
`cashflow.simular_flujo_de_caja` (proyección día a día, margen, fecha crítica,
apartado sugerido), `sugerencias_engine` (tres reglas con umbrales como
constantes) y el score de salud financiera. El prompt obliga al modelo a llamar
`simular_flujo_de_caja` para cualquier "¿me alcanza?" y le prohíbe calcular por
su cuenta. El modelo elige componentes y redacta; no suma.

## Consecuencias

- Los tests de los motores son rápidos, deterministas y sin red.
- El mismo motor sirve al chat, a las sugerencias proactivas y a la
  explicabilidad ([ADR 0020](0020-explicabilidad-por-componente.md)).
- El modelo a veces intenta "ayudar" con aritmética propia; se mitiga en el
  prompt, no se puede eliminar del todo.
- El motor no guarda historial de montos pasados; las reglas usan solo lo que el
  schema tiene hoy.
