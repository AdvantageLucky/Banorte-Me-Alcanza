from me_alcanza.mcp_bank.anomalias import detectar_picos_gasto


def test_detecta_pico_severo_por_encima_del_doble_del_promedio():
    resumen = [{"categoria": "restaurantes", "total": 2200.0, "count": 5}]
    historico = {"restaurantes": 1000.0}

    picos = detectar_picos_gasto(resumen, historico)

    assert len(picos) == 1
    assert picos[0]["categoria"] == "restaurantes"
    assert picos[0]["factor"] == 2.2
    assert picos[0]["severidad"] == "alta"


def test_detecta_pico_medio_entre_umbral_y_severo():
    resumen = [{"categoria": "transporte", "total": 1500.0, "count": 10}]
    historico = {"transporte": 1000.0}  # factor 1.5, entre 1.4 y 2.0

    picos = detectar_picos_gasto(resumen, historico)

    assert len(picos) == 1
    assert picos[0]["severidad"] == "media"


def test_no_marca_categoria_dentro_de_rango_normal():
    resumen = [{"categoria": "renta", "total": 1050.0, "count": 1}]
    historico = {"renta": 1000.0}  # factor 1.05, debajo del umbral

    assert detectar_picos_gasto(resumen, historico) == []


def test_ignora_categoria_sin_historial_suficiente():
    resumen = [{"categoria": "viajes", "total": 5000.0, "count": 1}]
    historico = {}  # sin promedio_historico > 0 para 'viajes'

    assert detectar_picos_gasto(resumen, historico) == []


def test_ordena_por_factor_descendente():
    resumen = [
        {"categoria": "a", "total": 150.0, "count": 1},
        {"categoria": "b", "total": 300.0, "count": 1},
    ]
    historico = {"a": 100.0, "b": 100.0}  # factores 1.5 y 3.0

    picos = detectar_picos_gasto(resumen, historico)

    assert [p["categoria"] for p in picos] == ["b", "a"]
