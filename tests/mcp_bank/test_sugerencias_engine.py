from datetime import date, timedelta

from me_alcanza.mcp_bank import sugerencias_engine as engine


def test_detectar_riesgo_liquidez_cuando_no_alcanza():
    hoy = date.today().isoformat()
    proxima_quincena = (date.today() + timedelta(days=10)).isoformat()
    ingresos = [{"monto": 100.0, "proxima_fecha": proxima_quincena}]
    gastos = [{"monto": 5000.0, "proxima_fecha": (date.today() + timedelta(days=2)).isoformat()}]
    candidatos = engine.detectar_riesgo_liquidez(saldo_actual=200.0, ingresos=ingresos, gastos=gastos, hoy=hoy)
    assert len(candidatos) == 1
    assert candidatos[0]["tipo"] == "riesgo_liquidez"
    assert candidatos[0]["entidad_id"] == "global"
    assert candidatos[0]["detalle"]["margen"] < 0


def test_detectar_riesgo_liquidez_cuando_si_alcanza():
    hoy = date.today().isoformat()
    proxima_quincena = (date.today() + timedelta(days=10)).isoformat()
    ingresos = [{"monto": 100000.0, "proxima_fecha": proxima_quincena}]
    gastos = []
    candidatos = engine.detectar_riesgo_liquidez(saldo_actual=5000.0, ingresos=ingresos, gastos=gastos, hoy=hoy)
    assert candidatos == []


def test_detectar_riesgo_liquidez_sin_ingresos_programados():
    hoy = date.today().isoformat()
    candidatos = engine.detectar_riesgo_liquidez(saldo_actual=100.0, ingresos=[], gastos=[], hoy=hoy)
    assert candidatos == []


def test_detectar_gastos_fijos_proximos_dispara_por_fecha_y_monto():
    hoy = date.today()
    gastos_fijos = [
        {"id": 1, "concepto": "Renta", "monto": 4000.0, "proxima_fecha": (hoy + timedelta(days=3)).isoformat()},
        {"id": 2, "concepto": "Internet", "monto": 500.0, "proxima_fecha": (hoy + timedelta(days=3)).isoformat()},
        {"id": 3, "concepto": "Seguro", "monto": 4000.0, "proxima_fecha": (hoy + timedelta(days=20)).isoformat()},
    ]
    candidatos = engine.detectar_gastos_fijos_proximos(gastos_fijos, saldo_actual=10000.0, hoy=hoy.isoformat())
    assert len(candidatos) == 1
    assert candidatos[0]["entidad_id"] == "1"
    assert candidatos[0]["detalle"]["concepto"] == "Renta"


def test_detectar_metas_en_riesgo_dispara_si_falta_poco_y_no_completada():
    hoy = date.today()
    metas = [
        {
            "id": 7,
            "descripcion": "Viaje",
            "monto_objetivo": 10000.0,
            "monto_ahorrado": 1000.0,
            "fecha_objetivo": (hoy + timedelta(days=15)).isoformat(),
        },
        {
            "id": 8,
            "descripcion": "Ya completada",
            "monto_objetivo": 500.0,
            "monto_ahorrado": 500.0,
            "fecha_objetivo": (hoy + timedelta(days=10)).isoformat(),
        },
        {
            "id": 9,
            "descripcion": "Falta mucho tiempo",
            "monto_objetivo": 500.0,
            "monto_ahorrado": 0.0,
            "fecha_objetivo": (hoy + timedelta(days=90)).isoformat(),
        },
    ]
    candidatos = engine.detectar_metas_en_riesgo(metas, hoy=hoy.isoformat())
    assert len(candidatos) == 1
    assert candidatos[0]["entidad_id"] == "7"
    assert candidatos[0]["detalle"]["descripcion"] == "Viaje"
