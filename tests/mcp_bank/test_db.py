from datetime import date, timedelta

import pytest
from me_alcanza.mcp_bank import db


def test_hash_password_no_es_igual_al_texto_plano():
    hashed = db.hash_password("pass123")
    assert hashed != "pass123"
    assert db.verify_password("pass123", hashed) is True


def test_verify_password_rechaza_password_incorrecta():
    hashed = db.hash_password("pass123")
    assert db.verify_password("otra-cosa", hashed) is False


@pytest.fixture
def conn():
    connection = db.get_connection(":memory:")
    db.seed(connection)
    yield connection
    connection.close()


def test_seed_crea_dos_usuarios(conn):
    assert db.autenticar(conn, "ana", "pass123") == "ana"
    assert db.autenticar(conn, "luis", "pass456") == "luis"


def test_autenticar_rechaza_password_incorrecta(conn):
    assert db.autenticar(conn, "ana", "wrong") is None


def test_autenticar_rechaza_usuario_inexistente(conn):
    assert db.autenticar(conn, "nadie", "x") is None


def test_seed_es_idempotente(conn):
    db.seed(conn)  # segunda llamada no debe duplicar ni fallar
    total = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    assert total == 2


def test_get_saldo(conn):
    assert db.get_saldo(conn, "ana") == {"saldo": 500.00, "moneda": "MXN"}


def test_get_saldo_cuenta_inexistente(conn):
    assert db.get_saldo(conn, "fantasma") is None


def test_get_cuenta(conn):
    cuenta = db.get_cuenta(conn, "luis")
    assert cuenta["numero_cuenta"] == "003344"
    assert cuenta["titular"] == "Luis Peña"
    assert cuenta["saldo"] == 8200.00


def test_get_movimientos_cuenta_nueva_esta_vacia(conn):
    assert db.get_movimientos(conn, "ana") == []


def test_get_ingresos_programados(conn):
    ingresos = db.get_ingresos_programados(conn, "ana")
    assert len(ingresos) == 1
    assert ingresos[0]["descripcion"] == "Nómina"
    assert ingresos[0]["monto"] == 12500.00
    assert ingresos[0]["frecuencia"] == "quincenal"
    assert ingresos[0]["proxima_fecha"] == (date.today() + timedelta(days=1)).isoformat()


def test_get_gastos_fijos(conn):
    gastos = db.get_gastos_fijos(conn, "ana")
    assert len(gastos) == 4
    conceptos = {g["concepto"] for g in gastos}
    assert conceptos == {"Agua", "Luz", "Colegiatura hijo 1", "Colegiatura hijo 2"}


def test_get_metas(conn):
    metas = db.get_metas(conn, "ana")
    assert len(metas) == 1
    assert metas[0]["monto_objetivo"] == 8000.00
    assert metas[0]["fecha_objetivo"] == (date.today() + timedelta(days=32)).isoformat()
    assert metas[0]["monto_ahorrado"] == 0


def test_buscar_contacto_por_alias_ambiguo(conn):
    resultados = db.buscar_contacto(conn, "ana", "pepe")
    assert len(resultados) == 2
    relaciones = {r["relacion"] for r in resultados}
    assert relaciones == {"hermano", "primo"}


def test_buscar_contacto_sin_resultados(conn):
    assert db.buscar_contacto(conn, "ana", "nadie-existe") == []


def test_ejecutar_transferencia_interna_mueve_saldo(conn):
    resultado = db.ejecutar_transferencia(
        conn, origen_id="luis", destino_cuenta="001122", monto=100.0, concepto="Pago"
    )
    assert resultado["ok"] is True
    assert resultado["nuevo_saldo"] == 8100.00
    assert db.get_saldo(conn, "ana")["saldo"] == 600.00


def test_ejecutar_transferencia_externa_solo_descuenta_origen(conn):
    resultado = db.ejecutar_transferencia(
        conn, origen_id="luis", destino_cuenta="999999", monto=50.0, concepto="Externo"
    )
    assert resultado["ok"] is True
    assert resultado["nuevo_saldo"] == 8150.00


def test_ejecutar_transferencia_rechaza_saldo_insuficiente(conn):
    with pytest.raises(ValueError):
        db.ejecutar_transferencia(
            conn, origen_id="ana", destino_cuenta="003344", monto=999999.0, concepto="x"
        )


def test_ejecutar_transferencia_rechaza_monto_no_positivo(conn):
    with pytest.raises(ValueError):
        db.ejecutar_transferencia(
            conn, origen_id="ana", destino_cuenta="003344", monto=0, concepto="x"
        )


def test_crear_apartado_descuenta_saldo_y_registra_meta(conn):
    meta_id = db.get_metas(conn, "ana")[0]["id"]
    resultado = db.crear_apartado(
        conn, account_id="ana", meta_id=meta_id, monto_por_periodo=100.0, periodicidad="semanal"
    )
    assert resultado["ok"] is True
    assert resultado["apartado"]["estado"] == "activo"
    assert db.get_saldo(conn, "ana")["saldo"] == 400.00
    assert db.get_metas(conn, "ana")[0]["monto_ahorrado"] == 100.0


def test_crear_apartado_rechaza_meta_de_otra_cuenta(conn):
    meta_id = db.get_metas(conn, "ana")[0]["id"]
    with pytest.raises(ValueError):
        db.crear_apartado(
            conn, account_id="luis", meta_id=meta_id, monto_por_periodo=50.0, periodicidad="semanal"
        )


def test_crear_apartado_rechaza_saldo_insuficiente(conn):
    meta_id = db.get_metas(conn, "ana")[0]["id"]
    with pytest.raises(ValueError):
        db.crear_apartado(
            conn, account_id="ana", meta_id=meta_id, monto_por_periodo=999999.0, periodicidad="semanal"
        )


def test_get_contacto_por_id(conn):
    contactos = db.buscar_contacto(conn, "ana", "pepe")
    contacto = db.get_contacto(conn, "ana", contactos[0]["id"])
    assert contacto == contactos[0]


def test_get_contacto_inexistente_devuelve_none(conn):
    assert db.get_contacto(conn, "ana", 999999) is None


def test_get_contacto_de_otra_cuenta_devuelve_none(conn):
    contactos = db.buscar_contacto(conn, "ana", "pepe")
    assert db.get_contacto(conn, "luis", contactos[0]["id"]) is None


def test_crear_contacto(conn):
    contacto = db.crear_contacto(conn, "ana", "Sofía López", "Sofi", "5566778899", "amiga")
    assert contacto["nombre"] == "Sofía López"
    assert contacto["id"] is not None
    assert len(db.buscar_contacto(conn, "ana", "sofi")) == 1


def test_actualizar_contacto(conn):
    contactos = db.buscar_contacto(conn, "ana", "pepe")
    contacto_id = contactos[0]["id"]
    actualizado = db.actualizar_contacto(
        conn, "ana", contacto_id, "José R. Actualizado", "Pepe2", "1112223333", "hermano"
    )
    assert actualizado["nombre"] == "José R. Actualizado"
    assert db.get_contacto(conn, "ana", contacto_id)["alias"] == "Pepe2"


def test_actualizar_contacto_inexistente(conn):
    with pytest.raises(ValueError):
        db.actualizar_contacto(conn, "ana", 999999, "x", "y", "z", "w")


def test_actualizar_contacto_de_otra_cuenta(conn):
    contactos = db.buscar_contacto(conn, "ana", "pepe")
    with pytest.raises(ValueError):
        db.actualizar_contacto(conn, "luis", contactos[0]["id"], "x", "y", "z", "w")


def test_eliminar_contacto(conn):
    contactos = db.buscar_contacto(conn, "ana", "pepe")
    contacto_id = contactos[0]["id"]
    db.eliminar_contacto(conn, "ana", contacto_id)
    assert db.get_contacto(conn, "ana", contacto_id) is None


def test_eliminar_contacto_de_otra_cuenta(conn):
    contactos = db.buscar_contacto(conn, "ana", "pepe")
    with pytest.raises(ValueError):
        db.eliminar_contacto(conn, "luis", contactos[0]["id"])


def test_crear_ingreso_programado(conn):
    ingreso = db.crear_ingreso_programado(
        conn, "ana", "Bono anual", 5000.0, "anual", "2026-12-01"
    )
    assert ingreso["id"] is not None
    assert ingreso["descripcion"] == "Bono anual"
    assert len(db.get_ingresos_programados(conn, "ana")) == 2


def test_crear_ingreso_programado_rechaza_monto_no_positivo(conn):
    with pytest.raises(ValueError):
        db.crear_ingreso_programado(conn, "ana", "x", 0, "mensual", "2026-12-01")


def test_actualizar_ingreso_programado(conn):
    ingreso_id = db.get_ingresos_programados(conn, "ana")[0]["id"]
    actualizado = db.actualizar_ingreso_programado(
        conn, "ana", ingreso_id, "Nómina actualizada", 13000.0, "quincenal", "2026-10-01"
    )
    assert actualizado["monto"] == 13000.0
    assert db.get_ingresos_programados(conn, "ana")[0]["descripcion"] == "Nómina actualizada"


def test_actualizar_ingreso_programado_inexistente(conn):
    with pytest.raises(ValueError):
        db.actualizar_ingreso_programado(conn, "ana", 999999, "x", 100.0, "mensual", "2026-10-01")


def test_actualizar_ingreso_programado_de_otra_cuenta(conn):
    ingreso_id = db.get_ingresos_programados(conn, "ana")[0]["id"]
    with pytest.raises(ValueError):
        db.actualizar_ingreso_programado(conn, "luis", ingreso_id, "x", 100.0, "mensual", "2026-10-01")


def test_eliminar_ingreso_programado(conn):
    ingreso_id = db.get_ingresos_programados(conn, "ana")[0]["id"]
    db.eliminar_ingreso_programado(conn, "ana", ingreso_id)
    assert db.get_ingresos_programados(conn, "ana") == []


def test_eliminar_ingreso_programado_de_otra_cuenta(conn):
    ingreso_id = db.get_ingresos_programados(conn, "ana")[0]["id"]
    with pytest.raises(ValueError):
        db.eliminar_ingreso_programado(conn, "luis", ingreso_id)


def test_crear_gasto_fijo(conn):
    gasto = db.crear_gasto_fijo(conn, "ana", "Internet", 600.0, "mensual", "2026-10-05")
    assert gasto["id"] is not None
    assert gasto["concepto"] == "Internet"
    assert len(db.get_gastos_fijos(conn, "ana")) == 5


def test_crear_gasto_fijo_rechaza_monto_no_positivo(conn):
    with pytest.raises(ValueError):
        db.crear_gasto_fijo(conn, "ana", "x", 0, "mensual", "2026-10-05")


def test_actualizar_gasto_fijo(conn):
    gasto_id = db.get_gastos_fijos(conn, "ana")[0]["id"]
    actualizado = db.actualizar_gasto_fijo(
        conn, "ana", gasto_id, "Agua actualizada", 350.0, "mensual", "2026-10-10"
    )
    assert actualizado["monto"] == 350.0


def test_actualizar_gasto_fijo_inexistente(conn):
    with pytest.raises(ValueError):
        db.actualizar_gasto_fijo(conn, "ana", 999999, "x", 100.0, "mensual", "2026-10-05")


def test_actualizar_gasto_fijo_de_otra_cuenta(conn):
    gasto_id = db.get_gastos_fijos(conn, "ana")[0]["id"]
    with pytest.raises(ValueError):
        db.actualizar_gasto_fijo(conn, "luis", gasto_id, "x", 100.0, "mensual", "2026-10-05")


def test_eliminar_gasto_fijo(conn):
    gasto_id = db.get_gastos_fijos(conn, "ana")[0]["id"]
    db.eliminar_gasto_fijo(conn, "ana", gasto_id)
    assert len(db.get_gastos_fijos(conn, "ana")) == 3


def test_eliminar_gasto_fijo_de_otra_cuenta(conn):
    gasto_id = db.get_gastos_fijos(conn, "ana")[0]["id"]
    with pytest.raises(ValueError):
        db.eliminar_gasto_fijo(conn, "luis", gasto_id)


def test_crear_meta(conn):
    meta = db.crear_meta(conn, "ana", "Viaje", 20000.0, "2027-01-01")
    assert meta["id"] is not None
    assert meta["monto_ahorrado"] == 0
    assert len(db.get_metas(conn, "ana")) == 2


def test_crear_meta_rechaza_monto_no_positivo(conn):
    with pytest.raises(ValueError):
        db.crear_meta(conn, "ana", "x", 0, "2027-01-01")


def test_actualizar_meta(conn):
    meta_id = db.get_metas(conn, "ana")[0]["id"]
    actualizada = db.actualizar_meta(conn, "ana", meta_id, "Concierto actualizado", 9000.0, "2027-02-01")
    assert actualizada["monto_objetivo"] == 9000.0
    # monto_ahorrado no se toca por un update
    assert actualizada["monto_ahorrado"] == 0


def test_actualizar_meta_inexistente(conn):
    with pytest.raises(ValueError):
        db.actualizar_meta(conn, "ana", 999999, "x", 100.0, "2027-01-01")


def test_actualizar_meta_de_otra_cuenta(conn):
    meta_id = db.get_metas(conn, "ana")[0]["id"]
    with pytest.raises(ValueError):
        db.actualizar_meta(conn, "luis", meta_id, "x", 100.0, "2027-01-01")


def test_eliminar_meta_sin_apartados(conn):
    meta_id = db.crear_meta(conn, "ana", "Meta borrable", 1000.0, "2027-01-01")["id"]
    db.eliminar_meta(conn, "ana", meta_id)
    assert all(m["id"] != meta_id for m in db.get_metas(conn, "ana"))


def test_eliminar_meta_con_apartado_activo_se_bloquea(conn):
    meta_id = db.get_metas(conn, "ana")[0]["id"]
    db.crear_apartado(conn, account_id="ana", meta_id=meta_id, monto_por_periodo=50.0, periodicidad="semanal")
    with pytest.raises(ValueError):
        db.eliminar_meta(conn, "ana", meta_id)


def test_eliminar_meta_de_otra_cuenta(conn):
    meta_id = db.get_metas(conn, "ana")[0]["id"]
    with pytest.raises(ValueError):
        db.eliminar_meta(conn, "luis", meta_id)


def test_listar_apartados_vacio(conn):
    assert db.listar_apartados(conn, "ana") == []


def test_listar_apartados_con_uno_activo(conn):
    meta_id = db.get_metas(conn, "ana")[0]["id"]
    db.crear_apartado(conn, account_id="ana", meta_id=meta_id, monto_por_periodo=50.0, periodicidad="semanal")
    apartados = db.listar_apartados(conn, "ana")
    assert len(apartados) == 1
    assert apartados[0]["estado"] == "activo"


def test_cancelar_apartado(conn):
    meta_id = db.get_metas(conn, "ana")[0]["id"]
    apartado_id = db.crear_apartado(
        conn, account_id="ana", meta_id=meta_id, monto_por_periodo=50.0, periodicidad="semanal"
    )["apartado"]["id"]
    cancelado = db.cancelar_apartado(conn, "ana", apartado_id)
    assert cancelado["estado"] == "cancelado"
    assert db.listar_apartados(conn, "ana")[0]["estado"] == "cancelado"


def test_cancelar_apartado_inexistente(conn):
    with pytest.raises(ValueError):
        db.cancelar_apartado(conn, "ana", 999999)


def test_cancelar_apartado_de_otra_cuenta(conn):
    meta_id = db.get_metas(conn, "ana")[0]["id"]
    apartado_id = db.crear_apartado(
        conn, account_id="ana", meta_id=meta_id, monto_por_periodo=50.0, periodicidad="semanal"
    )["apartado"]["id"]
    with pytest.raises(ValueError):
        db.cancelar_apartado(conn, "luis", apartado_id)


def test_migracion_categoria_es_idempotente(tmp_path):
    # Verificar que correr get_connection() dos veces sobre la misma DB file
    # es seguro (idempotente) — la segunda llamada debe capturar el OperationalError
    # cuando intente añadir la columna que ya existe.
    db_path = str(tmp_path / "test.db")

    # Primera llamada: crea la columna categoria
    conn1 = db.get_connection(db_path)
    columnas1 = [row["name"] for row in conn1.execute("PRAGMA table_info(movimientos)")]
    assert "categoria" in columnas1
    conn1.close()

    # Segunda llamada: sobre la misma DB file con la columna ya existente
    # debe capturar OperationalError y devolver una conexión válida
    conn2 = db.get_connection(db_path)
    columnas2 = [row["name"] for row in conn2.execute("PRAGMA table_info(movimientos)")]
    assert "categoria" in columnas2
    conn2.close()


def test_ejecutar_transferencia_categoriza_egreso_e_ingreso(conn):
    db.ejecutar_transferencia(
        conn, origen_id="luis", destino_cuenta="001122", monto=100.0, concepto="Pago"
    )
    egreso = conn.execute(
        "SELECT categoria FROM movimientos WHERE account_id = 'luis' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert egreso["categoria"] == "transferencia_enviada"
    ingreso = conn.execute(
        "SELECT categoria FROM movimientos WHERE account_id = 'ana' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert ingreso["categoria"] == "transferencia_recibida"


def test_crear_apartado_categoriza_como_ahorro(conn):
    meta_id = db.get_metas(conn, "ana")[0]["id"]
    db.crear_apartado(conn, account_id="ana", meta_id=meta_id, monto_por_periodo=50.0, periodicidad="semanal")
    fila = conn.execute(
        "SELECT categoria FROM movimientos WHERE account_id = 'ana' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert fila["categoria"] == "ahorro"


def test_get_resumen_movimientos_agrupa_por_categoria(conn):
    from datetime import date

    db.ejecutar_transferencia(conn, origen_id="luis", destino_cuenta="999999", monto=50.0, concepto="x")
    db.ejecutar_transferencia(conn, origen_id="luis", destino_cuenta="999999", monto=30.0, concepto="y")
    hoy = date.today().isoformat()
    resumen = db.get_resumen_movimientos(conn, "luis", hoy, hoy)
    assert len(resumen) == 1
    assert resumen[0]["categoria"] == "transferencia_enviada"
    assert resumen[0]["total"] == -80.0
    assert resumen[0]["count"] == 2


def test_get_resumen_movimientos_respeta_rango_de_fechas(conn):
    resumen = db.get_resumen_movimientos(conn, "luis", "2020-01-01", "2020-01-02")
    assert resumen == []


def test_get_resumen_movimientos_no_mezcla_cuentas(conn):
    from datetime import date

    db.ejecutar_transferencia(conn, origen_id="luis", destino_cuenta="999999", monto=50.0, concepto="x")
    hoy = date.today().isoformat()
    resumen_ana = db.get_resumen_movimientos(conn, "ana", hoy, hoy)
    assert resumen_ana == []


def test_crear_sugerencia_y_listar(conn):
    sugerencia = db.crear_sugerencia(
        conn, "ana", "gasto_fijo_proximo", "1", {"concepto": "Renta", "monto": 4000.0}
    )
    assert sugerencia["estado"] == "pendiente"
    assert sugerencia["detalle"] == {"concepto": "Renta", "monto": 4000.0}
    listado = db.listar_sugerencias(conn, "ana")
    assert len(listado) == 1
    assert listado[0]["tipo"] == "gasto_fijo_proximo"


def test_existe_sugerencia_pendiente(conn):
    assert db.existe_sugerencia_pendiente(conn, "ana", "meta_en_riesgo", "7") is False
    db.crear_sugerencia(conn, "ana", "meta_en_riesgo", "7", {"x": 1})
    assert db.existe_sugerencia_pendiente(conn, "ana", "meta_en_riesgo", "7") is True


def test_listar_sugerencias_filtra_por_estado(conn):
    s1 = db.crear_sugerencia(conn, "ana", "meta_en_riesgo", "7", {"x": 1})
    db.crear_sugerencia(conn, "ana", "gasto_fijo_proximo", "1", {"y": 2})
    db.marcar_sugerencia(conn, "ana", s1["id"], "atendida")
    pendientes = db.listar_sugerencias(conn, "ana", estado="pendiente")
    assert len(pendientes) == 1
    assert pendientes[0]["tipo"] == "gasto_fijo_proximo"


def test_listar_sugerencias_no_mezcla_cuentas(conn):
    db.crear_sugerencia(conn, "ana", "meta_en_riesgo", "7", {"x": 1})
    assert db.listar_sugerencias(conn, "luis") == []


def test_marcar_sugerencia_atendida(conn):
    s = db.crear_sugerencia(conn, "ana", "meta_en_riesgo", "7", {"x": 1})
    actualizada = db.marcar_sugerencia(conn, "ana", s["id"], "atendida")
    assert actualizada["estado"] == "atendida"
    assert actualizada["resuelta_at"] is not None


def test_marcar_sugerencia_de_otra_cuenta_falla(conn):
    s = db.crear_sugerencia(conn, "ana", "meta_en_riesgo", "7", {"x": 1})
    with pytest.raises(ValueError):
        db.marcar_sugerencia(conn, "luis", s["id"], "atendida")


def test_marcar_sugerencia_estado_invalido_falla(conn):
    s = db.crear_sugerencia(conn, "ana", "meta_en_riesgo", "7", {"x": 1})
    with pytest.raises(ValueError):
        db.marcar_sugerencia(conn, "ana", s["id"], "estado_invalido")
