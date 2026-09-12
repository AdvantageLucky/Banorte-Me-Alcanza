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
