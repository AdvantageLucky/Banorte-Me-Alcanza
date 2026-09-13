from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class _Evento:
    fecha: date
    monto: float  # positivo = ingreso, negativo = gasto


def _parse_fecha(fecha_str: str) -> date:
    return datetime.strptime(fecha_str, "%Y-%m-%d").date()


def simular_flujo_de_caja(
    saldo_actual: float,
    ingresos: list[dict],
    gastos: list[dict],
    hoy: str,
    fecha_objetivo: str,
    monto_objetivo: float,
) -> dict:
    hoy_fecha = _parse_fecha(hoy)
    objetivo = _parse_fecha(fecha_objetivo)
    if objetivo < hoy_fecha:
        raise ValueError("fecha_objetivo no puede ser anterior a hoy")

    eventos = [
        _Evento(_parse_fecha(i["proxima_fecha"]), i["monto"]) for i in ingresos
    ] + [
        _Evento(_parse_fecha(g["proxima_fecha"]), -g["monto"]) for g in gastos
    ]
    eventos = [e for e in eventos if hoy_fecha <= e.fecha <= objetivo]
    eventos.sort(key=lambda e: (e.fecha, 0 if e.monto >= 0 else 1))

    running = saldo_actual
    minimo_historico = saldo_actual
    fecha_minimo_historico: date | None = None
    # Serie determinista del saldo proyectado, punto por evento (nunca día a
    # día relleno artificialmente) — es la fuente real de datos para
    # graficar la proyección en un LineChart, en vez de reconstruirla a
    # mano en el prompt o dejar que el LLM la invente.
    serie = [{"fecha": hoy_fecha.isoformat(), "saldo": round(saldo_actual, 2)}]

    for evento in eventos:
        running += evento.monto
        serie.append({"fecha": evento.fecha.isoformat(), "saldo": round(running, 2)})
        if running < minimo_historico:
            minimo_historico = running
            fecha_minimo_historico = evento.fecha

    running_final = running - monto_objetivo
    serie.append({"fecha": objetivo.isoformat(), "saldo": round(running_final, 2)})
    if running_final < minimo_historico:
        margen = running_final
        fecha_critica = objetivo
    else:
        margen = minimo_historico
        fecha_critica = fecha_minimo_historico

    alcanza = margen >= 0
    saldo_minimo_proyectado = round(minimo_historico, 2)
    margen = round(margen, 2)

    apartado_sugerido = None
    if not alcanza:
        dias = max((objetivo - hoy_fecha).days, 1)
        num_periodos = max(dias // 7, 1)
        deficit = -margen
        monto_por_periodo = round(deficit / num_periodos, 2)
        apartado_sugerido = {
            "monto_por_periodo": monto_por_periodo,
            "periodicidad": "semanal",
            "num_periodos": num_periodos,
        }

    return {
        "alcanza": alcanza,
        "saldo_minimo_proyectado": saldo_minimo_proyectado,
        "fecha_critica": fecha_critica.isoformat() if fecha_critica else None,
        "margen": margen,
        "apartado_sugerido": apartado_sugerido,
        "serie": serie,
    }
