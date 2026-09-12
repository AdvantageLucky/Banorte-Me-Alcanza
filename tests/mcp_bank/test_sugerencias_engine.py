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


def test_score_perfecto_sin_riesgos_ni_apartados():
    resultado = engine.calcular_score_salud_financiera(
        saldo_actual=10000.0, ingresos=[], gastos=[], metas=[], apartados_activos=0, hoy=date.today().isoformat()
    )
    assert resultado["score"] == 100
    assert resultado["categoria"] == "Saludable"


def test_score_baja_con_riesgo_de_liquidez():
    # Nota: el mismo gasto (5000, en +2 días, >= 30% del saldo de 200) dispara
    # AMBAS reglas: riesgo_liquidez (-30) y gasto_fijo_proximo (-5, 1 gasto).
    # Score esperado: 100 - 30 - 5 = 65.
    hoy = date.today()
    ingresos = [{"monto": 100.0, "proxima_fecha": (hoy + timedelta(days=10)).isoformat()}]
    gastos = [{"id": 1, "concepto": "Gasto", "monto": 5000.0, "proxima_fecha": (hoy + timedelta(days=2)).isoformat()}]
    resultado = engine.calcular_score_salud_financiera(
        saldo_actual=200.0, ingresos=ingresos, gastos=gastos, metas=[], apartados_activos=0, hoy=hoy.isoformat()
    )
    assert resultado["score"] == 65
    assert any("saldo" in f.lower() for f in resultado["factores"])


def test_score_penaliza_saldo_no_positivo_sin_ingresos_rastreados():
    # Sin ingresos rastreados, detectar_riesgo_liquidez nunca dispara. El saldo
    # en 0 (o negativo) debe penalizarse igual mediante el fallback elif.
    resultado = engine.calcular_score_salud_financiera(
        saldo_actual=0.0, ingresos=[], gastos=[], metas=[], apartados_activos=0, hoy=date.today().isoformat()
    )
    assert resultado["score"] == 100 - engine.PENALIZACION_SALDO_NO_POSITIVO
    assert resultado["categoria"] != "Saludable"
    assert any("saldo" in f.lower() for f in resultado["factores"])


def test_score_penaliza_saldo_negativo_sin_ingresos_rastreados():
    resultado = engine.calcular_score_salud_financiera(
        saldo_actual=-500.0, ingresos=[], gastos=[], metas=[], apartados_activos=0, hoy=date.today().isoformat()
    )
    assert resultado["score"] == 100 - engine.PENALIZACION_SALDO_NO_POSITIVO
    assert resultado["categoria"] != "Saludable"
    assert any("saldo" in f.lower() for f in resultado["factores"])


def test_score_sube_con_apartado_activo():
    resultado = engine.calcular_score_salud_financiera(
        saldo_actual=10000.0, ingresos=[], gastos=[], metas=[], apartados_activos=1, hoy=date.today().isoformat()
    )
    assert resultado["score"] == 100  # ya estaba en el tope, el clamp no deja subir de 100
    assert any("ahorro" in f.lower() for f in resultado["factores"])


def test_score_categoria_riesgo_cuando_muy_bajo():
    # riesgo_liquidez (-30) + gasto_fijo_proximo (-5, 1 gasto) + 3 metas en
    # riesgo (min(3*10, 20) = -20). Score esperado: 100 - 30 - 5 - 20 = 45.
    hoy = date.today()
    ingresos = [{"monto": 100.0, "proxima_fecha": (hoy + timedelta(days=10)).isoformat()}]
    gastos = [{"id": 1, "concepto": "Gasto", "monto": 5000.0, "proxima_fecha": (hoy + timedelta(days=2)).isoformat()}]
    metas = [
        {"id": i, "descripcion": f"Meta {i}", "monto_objetivo": 100.0, "monto_ahorrado": 0.0,
         "fecha_objetivo": (hoy + timedelta(days=5)).isoformat()}
        for i in range(3)
    ]
    resultado = engine.calcular_score_salud_financiera(
        saldo_actual=200.0, ingresos=ingresos, gastos=gastos, metas=metas, apartados_activos=0, hoy=hoy.isoformat()
    )
    assert resultado["score"] == 45
    assert resultado["categoria"] == "Riesgo"
