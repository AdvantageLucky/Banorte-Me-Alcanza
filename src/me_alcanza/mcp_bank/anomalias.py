"""Detección determinista de picos/anomalías de gasto por categoría.

Compara el gasto real del periodo actual contra el promedio real de esa
MISMA cuenta en periodos anteriores (ver
`db.get_promedio_historico_por_categoria`) — nunca contra un umbral fijo
inventado ni contra el gasto de otro usuario. Vive separado de
`sugerencias_engine.py` porque no es una regla de riesgo financiero
(liquidez, gasto próximo, meta) sino una comparación estadística simple
sobre patrones de gasto; ambas son igual de deterministas.
"""

UMBRAL_PICO = 1.4  # 40% por encima del promedio histórico
UMBRAL_PICO_SEVERO = 2.0  # el doble del promedio histórico


def detectar_picos_gasto(
    resumen_actual: list[dict],
    promedio_historico: dict[str, float],
) -> list[dict]:
    """Devuelve las categorías cuyo gasto actual excede su propio promedio
    histórico por UMBRAL_PICO o más.

    Args:
      resumen_actual: salida de get_resumen_movimientos, [{categoria, total, count}, ...].
      promedio_historico: salida de get_promedio_historico_por_categoria, {categoria: promedio}.

    Returns:
      Lista de {categoria, total_actual, promedio_historico, factor, severidad}
      ordenada por factor descendente. severidad es 'alta' (>= UMBRAL_PICO_SEVERO)
      o 'media' (>= UMBRAL_PICO).
    """
    picos = []
    for fila in resumen_actual:
        categoria = fila["categoria"]
        total_actual = fila["total"]
        promedio = promedio_historico.get(categoria, 0.0)
        if promedio <= 0:
            # Sin historial suficiente para juzgar si es un pico: no se
            # inventa una comparación contra cero.
            continue
        factor = total_actual / promedio
        if factor < UMBRAL_PICO:
            continue
        picos.append(
            {
                "categoria": categoria,
                "total_actual": total_actual,
                "promedio_historico": round(promedio, 2),
                "factor": round(factor, 2),
                "severidad": "alta" if factor >= UMBRAL_PICO_SEVERO else "media",
            }
        )
    picos.sort(key=lambda p: p["factor"], reverse=True)
    return picos
