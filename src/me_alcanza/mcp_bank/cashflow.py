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
    minimo = saldo_actual
    fecha_critica: date | None = None

    for evento in eventos:
        running += evento.monto
        if running < minimo:
            minimo = running
            fecha_critica = evento.fecha

    running -= monto_objetivo
    if running < minimo:
        minimo = running
        fecha_critica = objetivo

    alcanza = minimo >= 0
    margen = round(minimo, 2)

    apartado_sugerido = None
    if not alcanza:
        dias = max((objetivo - hoy_fecha).days, 1)
        num_periodos = max(dias // 7, 1)
        deficit = -minimo
        monto_por_periodo = round(deficit / num_periodos, 2)
        apartado_sugerido = {
            "monto_por_periodo": monto_por_periodo,
            "periodicidad": "semanal",
            "num_periodos": num_periodos,
        }

    return {
        "alcanza": alcanza,
        "saldo_minimo_proyectado": margen,
        "fecha_critica": fecha_critica.isoformat() if fecha_critica else None,
        "margen": margen,
        "apartado_sugerido": apartado_sugerido,
    }
