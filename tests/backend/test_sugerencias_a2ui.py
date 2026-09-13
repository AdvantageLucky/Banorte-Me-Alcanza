from me_alcanza.backend.sugerencias_a2ui import construir_tarjeta_sugerencia


def _sugerencia(tipo: str, detalle: dict, sugerencia_id: int = 1) -> dict:
    return {"id": sugerencia_id, "tipo": tipo, "entidad_id": "x", "detalle": detalle}


def test_construir_tarjeta_riesgo_liquidez_incluye_el_titulo_y_el_monto():
    tarjeta = construir_tarjeta_sugerencia(
        _sugerencia("riesgo_liquidez", {"margen": -150.5, "fecha_critica": "2026-09-15", "saldo_minimo_proyectado": -150.5})
    )
    textos = [c["text"] for c in tarjeta[1]["updateComponents"]["components"] if c["component"] == "Text"]
    assert "Riesgo de saldo negativo" in textos
    assert any("$-150.50" in t and "15 sep 2026" in t for t in textos)


def test_construir_tarjeta_gasto_fijo_proximo():
    tarjeta = construir_tarjeta_sugerencia(
        _sugerencia("gasto_fijo_proximo", {"concepto": "Agua", "monto": 320.0, "proxima_fecha": "2026-09-15"})
    )
    textos = [c["text"] for c in tarjeta[1]["updateComponents"]["components"] if c["component"] == "Text"]
    assert "Pago próximo: Agua" in textos
    assert any("$320.00" in t and "15 sep 2026" in t for t in textos)


def test_construir_tarjeta_meta_en_riesgo():
    tarjeta = construir_tarjeta_sugerencia(
        _sugerencia(
            "meta_en_riesgo",
            {"descripcion": "Viaje", "monto_objetivo": 1000.0, "monto_ahorrado": 200.0, "fecha_objetivo": "2026-12-01"},
        )
    )
    textos = [c["text"] for c in tarjeta[1]["updateComponents"]["components"] if c["component"] == "Text"]
    assert "Meta en riesgo: Viaje" in textos
    assert any("$200.00" in t and "$1,000.00" in t and "01 dic 2026" in t for t in textos)


def test_construir_tarjeta_incluye_los_botones_con_el_sugerencia_id_correcto():
    tarjeta = construir_tarjeta_sugerencia(_sugerencia("gasto_fijo_proximo", {"concepto": "Luz", "monto": 1, "proxima_fecha": "2026-09-15"}, sugerencia_id=42))
    componentes = tarjeta[1]["updateComponents"]["components"]
    botones = [c for c in componentes if c["component"] == "Button"]
    assert len(botones) == 2

    atender = next(b for b in botones if b["action"]["event"]["name"] == "atender_sugerencia")
    descartar = next(b for b in botones if b["action"]["event"]["name"] == "descartar_sugerencia")
    assert atender["variant"] == "primary"
    assert atender["action"]["event"]["context"] == {"sugerenciaId": 42}
    assert descartar["action"]["event"]["context"] == {"sugerenciaId": 42}


def test_construir_tarjeta_genera_un_surface_id_distinto_cada_vez():
    detalle = {"concepto": "Luz", "monto": 1, "proxima_fecha": "2026-09-15"}
    tarjeta_1 = construir_tarjeta_sugerencia(_sugerencia("gasto_fijo_proximo", detalle, sugerencia_id=1))
    tarjeta_2 = construir_tarjeta_sugerencia(_sugerencia("gasto_fijo_proximo", detalle, sugerencia_id=1))
    assert tarjeta_1[0]["createSurface"]["surfaceId"] != tarjeta_2[0]["createSurface"]["surfaceId"]
