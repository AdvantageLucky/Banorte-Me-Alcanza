# ADR 0020 — Explicabilidad: todo número derivado lleva un "¿Cómo se calculó?"

**Estado:** Aceptada · 2026-09-12

## Contexto

Un veredicto "no te alcanza por $570" sin sus entradas no es accionable: el
usuario no sabe si el modelo contó la nómina, si olvidó un gasto, o si puede
mover algo para que sí alcance. El brief pide interfaces que *resuelvan*, no
que sentencien.

## Decisión

El prompt de UI exige que cualquier tarjeta con un número calculado (margen,
saldo proyectado, desglose de una transferencia, score) incluya un componente
`Modal` del catálogo cuyo trigger es un `Text` caption "¿Cómo se calculó?" y
cuyo contenido lista los montos y fechas concretos que entraron al cálculo. Los
motores deterministas devuelven esos factores explícitamente (`fecha_critica`,
`saldo_minimo_proyectado`, los factores del score) para que el modelo tenga qué
mostrar. No se agrega el modal a valores directos de una tool (el saldo tal
cual).

## Consecuencias

- La explicación sale de datos reales del motor, no de una racionalización del
  modelo.
- El prompt es más largo y el modelo a veces omite el modal; se verifica
  manualmente en la demo.
- El `Modal` del catálogo básico se renderiza a sí mismo con trigger y content
  como hijos; hubo que ajustar estilos (cursor, clases) en el renderer web.
