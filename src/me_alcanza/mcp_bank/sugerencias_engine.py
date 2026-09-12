from datetime import date, datetime

from . import cashflow

DIAS_UMBRAL_GASTO_PROXIMO = 5
PCT_UMBRAL_GASTO_PROXIMO = 0.30
DIAS_UMBRAL_META_EN_RIESGO = 30


def _parse_fecha(fecha_str: str) -> date:
    return datetime.strptime(fecha_str, "%Y-%m-%d").date()


def detectar_riesgo_liquidez(
    saldo_actual: float, ingresos: list[dict], gastos: list[dict], hoy: str
) -> list[dict]:
    candidatos = []
    for ingreso in ingresos:
        resultado = cashflow.simular_flujo_de_caja(
            saldo_actual=saldo_actual,
            ingresos=ingresos,
            gastos=gastos,
            hoy=hoy,
            fecha_objetivo=ingreso["proxima_fecha"],
            monto_objetivo=0,
        )
        if not resultado["alcanza"]:
            candidatos.append(
                {
                    "tipo": "riesgo_liquidez",
                    "entidad_id": "global",
                    "detalle": {
                        "margen": resultado["margen"],
                        "fecha_critica": resultado["fecha_critica"],
                        "saldo_minimo_proyectado": resultado["saldo_minimo_proyectado"],
                    },
                }
            )
            break  # una sola alerta de liquidez basta, aunque haya varios ingresos
    return candidatos


def detectar_gastos_fijos_proximos(gastos_fijos: list[dict], saldo_actual: float, hoy: str) -> list[dict]:
    hoy_fecha = _parse_fecha(hoy)
    candidatos = []
    for gasto in gastos_fijos:
        dias_restantes = (_parse_fecha(gasto["proxima_fecha"]) - hoy_fecha).days
        if dias_restantes < 0 or dias_restantes > DIAS_UMBRAL_GASTO_PROXIMO:
            continue
        if saldo_actual <= 0 or gasto["monto"] < PCT_UMBRAL_GASTO_PROXIMO * saldo_actual:
            continue
        candidatos.append(
            {
                "tipo": "gasto_fijo_proximo",
                "entidad_id": str(gasto["id"]),
                "detalle": {
                    "concepto": gasto["concepto"],
                    "monto": gasto["monto"],
                    "proxima_fecha": gasto["proxima_fecha"],
                },
            }
        )
    return candidatos


def detectar_metas_en_riesgo(metas: list[dict], hoy: str) -> list[dict]:
    hoy_fecha = _parse_fecha(hoy)
    candidatos = []
    for meta in metas:
        if meta["monto_ahorrado"] >= meta["monto_objetivo"]:
            continue
        dias_restantes = (_parse_fecha(meta["fecha_objetivo"]) - hoy_fecha).days
        if dias_restantes < 0 or dias_restantes > DIAS_UMBRAL_META_EN_RIESGO:
            continue
        candidatos.append(
            {
                "tipo": "meta_en_riesgo",
                "entidad_id": str(meta["id"]),
                "detalle": {
                    "descripcion": meta["descripcion"],
                    "monto_objetivo": meta["monto_objetivo"],
                    "monto_ahorrado": meta["monto_ahorrado"],
                    "fecha_objetivo": meta["fecha_objetivo"],
                },
            }
        )
    return candidatos


PENALIZACION_RIESGO_LIQUIDEZ = 30
PENALIZACION_POR_GASTO_PROXIMO = 5
PENALIZACION_MAX_GASTOS = 20
PENALIZACION_POR_META_EN_RIESGO = 10
PENALIZACION_MAX_METAS = 20
BONO_APARTADO_ACTIVO = 10


def calcular_score_salud_financiera(
    saldo_actual: float,
    ingresos: list[dict],
    gastos: list[dict],
    metas: list[dict],
    apartados_activos: int,
    hoy: str,
) -> dict:
    riesgo_liquidez = detectar_riesgo_liquidez(saldo_actual, ingresos, gastos, hoy)
    gastos_proximos = detectar_gastos_fijos_proximos(gastos, saldo_actual, hoy)
    metas_en_riesgo = detectar_metas_en_riesgo(metas, hoy)

    score = 100
    factores = []

    if riesgo_liquidez:
        score -= PENALIZACION_RIESGO_LIQUIDEZ
        factores.append("Tu saldo se proyecta insuficiente antes de tu próximo ingreso programado.")

    penalizacion_gastos = min(len(gastos_proximos) * PENALIZACION_POR_GASTO_PROXIMO, PENALIZACION_MAX_GASTOS)
    if penalizacion_gastos:
        factores.append(
            f"{len(gastos_proximos)} gasto(s) fijo(s) próximo(s) representan una parte alta de tu saldo actual."
        )
        score -= penalizacion_gastos

    penalizacion_metas = min(len(metas_en_riesgo) * PENALIZACION_POR_META_EN_RIESGO, PENALIZACION_MAX_METAS)
    if penalizacion_metas:
        factores.append(f"{len(metas_en_riesgo)} meta(s) de ahorro en riesgo de no cumplirse a tiempo.")
        score -= penalizacion_metas

    if apartados_activos > 0:
        score += BONO_APARTADO_ACTIVO
        factores.append("Tienes al menos un apartado de ahorro activo — buen hábito.")

    score = max(0, min(100, score))

    if score >= 80:
        categoria = "Saludable"
    elif score >= 50:
        categoria = "Atención"
    else:
        categoria = "Riesgo"

    if not factores:
        factores.append("No se detectaron riesgos ni hábitos destacados en este momento.")

    return {"score": score, "categoria": categoria, "factores": factores}
