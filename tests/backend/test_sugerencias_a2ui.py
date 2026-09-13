from me_alcanza.backend.sugerencias_a2ui import construir_tarjeta_sugerencia


def _sugerencia(tipo: str, detalle: dict, sugerencia_id: int = 1) -> dict:
    return {"id": sugerencia_id, "tipo": tipo, "entidad_id": "x", "detalle": detalle}


def _stat_card(tarjeta):
    componentes = tarjeta[1]["updateComponents"]["components"]
    return next(c for c in componentes if c["component"] == "StatCard")


def test_construir_tarjeta_riesgo_liquidez_incluye_el_titulo_y_el_monto():
    tarjeta = construir_tarjeta_sugerencia(
        _sugerencia("riesgo_liquidez", {"margen": -150.5, "fecha_critica": "2026-09-15", "saldo_minimo_proyectado": -150.5})
    )
    componentes = tarjeta[1]["updateComponents"]["components"]
    titulo = next(c["text"] for c in componentes if c["id"] == "titulo")
    assert titulo == "Riesgo de saldo negativo"
    stat = _stat_card(tarjeta)
    assert stat["value"] == "$-150.50"
    assert "15 sep 2026" in stat["trendLabel"]
    assert stat["tone"] == "negative"


def test_construir_tarjeta_gasto_fijo_proximo():
    tarjeta = construir_tarjeta_sugerencia(
        _sugerencia("gasto_fijo_proximo", {"concepto": "Agua", "monto": 320.0, "proxima_fecha": "2026-09-15"})
    )
    componentes = tarjeta[1]["updateComponents"]["components"]
    titulo = next(c["text"] for c in componentes if c["id"] == "titulo")
    assert titulo == "Pago próximo: Agua"
    stat = _stat_card(tarjeta)
    assert stat["value"] == "$320.00"
    assert "15 sep 2026" in stat["trendLabel"]
    assert stat["tone"] == "warning"


def test_construir_tarjeta_meta_en_riesgo():
    tarjeta = construir_tarjeta_sugerencia(
        _sugerencia(
            "meta_en_riesgo",
            {"descripcion": "Viaje", "monto_objetivo": 1000.0, "monto_ahorrado": 200.0, "fecha_objetivo": "2026-12-01"},
        )
    )
    componentes = tarjeta[1]["updateComponents"]["components"]
    titulo = next(c["text"] for c in componentes if c["id"] == "titulo")
    assert titulo == "Meta en riesgo: Viaje"
    stat = _stat_card(tarjeta)
    assert "$200.00" in stat["value"] and "$1,000.00" in stat["value"]
    assert "01 dic 2026" in stat["trendLabel"]
    assert stat["tone"] == "warning"


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


def test_envelopes_usan_version_v0_9():
    # a2ui_core (Flutter) lanza A2uiValidationError si version != "v0.9";
    # el resto del backend (orchestrator, fake_provider) ya usa "v0.9".
    sugerencia = {
        "id": 1,
        "tipo": "gasto_fijo_proximo",
        "detalle": {"concepto": "Agua", "monto": 320.0, "proxima_fecha": "2026-09-15"},
        "estado": "pendiente",
    }
    mensajes = construir_tarjeta_sugerencia(sugerencia)
    assert {m["version"] for m in mensajes} == {"v0.9"}
