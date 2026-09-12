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
