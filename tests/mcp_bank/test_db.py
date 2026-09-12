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
