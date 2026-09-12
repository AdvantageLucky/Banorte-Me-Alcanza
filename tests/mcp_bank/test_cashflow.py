import pytest
from me_alcanza.mcp_bank.cashflow import simular_flujo_de_caja

INGRESOS = [
    {"monto": 12500.00, "proxima_fecha": "2026-09-12"},
]
GASTOS = [
    {"monto": 320.00, "proxima_fecha": "2026-09-14"},
    {"monto": 450.00, "proxima_fecha": "2026-09-14"},
    {"monto": 2400.00, "proxima_fecha": "2026-09-15"},
    {"monto": 2400.00, "proxima_fecha": "2026-09-15"},
]


def test_alcanza_con_margen_amplio():
    resultado = simular_flujo_de_caja(
        saldo_actual=500.00,
        ingresos=INGRESOS,
        gastos=GASTOS,
        hoy="2026-09-11",
        fecha_objetivo="2026-10-13",
        monto_objetivo=1000.00,
    )
    assert resultado["alcanza"] is True
    assert resultado["apartado_sugerido"] is None


def test_no_alcanza_sugiere_apartado():
    resultado = simular_flujo_de_caja(
        saldo_actual=500.00,
        ingresos=INGRESOS,
        gastos=GASTOS,
        hoy="2026-09-11",
        fecha_objetivo="2026-10-13",
        monto_objetivo=8000.00,
    )
    assert resultado["alcanza"] is False
    assert resultado["margen"] == pytest.approx(-570.0)
    assert resultado["fecha_critica"] == "2026-10-13"
    apartado = resultado["apartado_sugerido"]
    assert apartado is not None
    assert apartado["periodicidad"] == "semanal"
    assert apartado["num_periodos"] == 4
    assert apartado["monto_por_periodo"] == pytest.approx(142.5)


def test_fecha_critica_puede_ser_anterior_a_la_fecha_objetivo():
    # El valle ocurre al pagar los gastos fijos (9/15); un ingreso posterior
    # recupera el saldo antes de llegar a fecha_objetivo, así que el mínimo
    # histórico (y su fecha) quedan fijados en el valle, no en la meta.
    resultado = simular_flujo_de_caja(
        saldo_actual=1000.00,
        ingresos=[{"monto": 6000.00, "proxima_fecha": "2026-09-20"}],
        gastos=GASTOS,
        hoy="2026-09-11",
        fecha_objetivo="2026-10-13",
        monto_objetivo=100.00,
    )
    assert resultado["alcanza"] is False
    assert resultado["fecha_critica"] == "2026-09-15"
    assert resultado["margen"] == pytest.approx(-4570.0)


def test_fecha_objetivo_en_el_pasado_lanza_error():
    with pytest.raises(ValueError):
        simular_flujo_de_caja(
            saldo_actual=500.00,
            ingresos=INGRESOS,
            gastos=GASTOS,
            hoy="2026-09-11",
            fecha_objetivo="2026-01-01",
            monto_objetivo=100.00,
        )


def test_eventos_posteriores_a_fecha_objetivo_se_ignoran():
    resultado = simular_flujo_de_caja(
        saldo_actual=100.00,
        ingresos=[{"monto": 5000.00, "proxima_fecha": "2026-12-01"}],
        gastos=[],
        hoy="2026-09-11",
        fecha_objetivo="2026-10-13",
        monto_objetivo=50.00,
    )
    assert resultado["alcanza"] is True
    assert resultado["margen"] == pytest.approx(50.0)
