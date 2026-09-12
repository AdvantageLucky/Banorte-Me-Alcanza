import hashlib
import hmac
import os
import sqlite3
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    account_id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    nombre TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cuentas (
    account_id TEXT PRIMARY KEY REFERENCES usuarios(account_id),
    numero_cuenta TEXT UNIQUE NOT NULL,
    saldo REAL NOT NULL,
    moneda TEXT NOT NULL DEFAULT 'MXN'
);
CREATE TABLE IF NOT EXISTS movimientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL REFERENCES usuarios(account_id),
    fecha TEXT NOT NULL,
    concepto TEXT NOT NULL,
    monto REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS ingresos_programados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL REFERENCES usuarios(account_id),
    descripcion TEXT NOT NULL,
    monto REAL NOT NULL,
    frecuencia TEXT NOT NULL,
    proxima_fecha TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gastos_fijos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL REFERENCES usuarios(account_id),
    concepto TEXT NOT NULL,
    monto REAL NOT NULL,
    frecuencia TEXT NOT NULL,
    proxima_fecha TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL REFERENCES usuarios(account_id),
    descripcion TEXT NOT NULL,
    monto_objetivo REAL NOT NULL,
    fecha_objetivo TEXT NOT NULL,
    monto_ahorrado REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS apartados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL REFERENCES usuarios(account_id),
    meta_id INTEGER NOT NULL REFERENCES metas(id),
    monto_por_periodo REAL NOT NULL,
    periodicidad TEXT NOT NULL,
    fecha_inicio TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'activo'
);
CREATE TABLE IF NOT EXISTS contactos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id_titular TEXT NOT NULL REFERENCES usuarios(account_id),
    nombre TEXT NOT NULL,
    alias TEXT NOT NULL,
    cuenta_destino TEXT NOT NULL,
    relacion TEXT NOT NULL
);
"""

_PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    salt_hex, digest_hex = password_hash.split("$")
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(digest_hex)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return hmac.compare_digest(actual, expected)


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def seed(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    if existing > 0:
        return

    conn.execute(
        "INSERT INTO usuarios (account_id, username, password_hash, nombre) VALUES (?, ?, ?, ?)",
        ("ana", "ana", hash_password("pass123"), "Ana Torres"),
    )
    conn.execute(
        "INSERT INTO cuentas (account_id, numero_cuenta, saldo, moneda) VALUES (?, ?, ?, ?)",
        ("ana", "001122", 500.00, "MXN"),
    )
    conn.execute(
        """
        INSERT INTO ingresos_programados (account_id, descripcion, monto, frecuencia, proxima_fecha)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("ana", "Nómina", 12500.00, "quincenal", "2026-09-12"),
    )
    for concepto, monto, fecha in [
        ("Agua", 320.00, "2026-09-14"),
        ("Luz", 450.00, "2026-09-14"),
        ("Colegiatura hijo 1", 2400.00, "2026-09-15"),
        ("Colegiatura hijo 2", 2400.00, "2026-09-15"),
    ]:
        conn.execute(
            """
            INSERT INTO gastos_fijos (account_id, concepto, monto, frecuencia, proxima_fecha)
            VALUES (?, ?, ?, 'mensual', ?)
            """,
            ("ana", concepto, monto, fecha),
        )
    conn.execute(
        """
        INSERT INTO metas (account_id, descripcion, monto_objetivo, fecha_objetivo)
        VALUES (?, ?, ?, ?)
        """,
        ("ana", "Concierto (boletos + viaje)", 8000.00, "2026-10-13"),
    )
    for nombre, alias, cuenta_destino, relacion in [
        ("José Ramírez", "Pepe", "9988776655", "hermano"),
        ("José Torres", "Pepe", "1122334455", "primo"),
    ]:
        conn.execute(
            """
            INSERT INTO contactos (account_id_titular, nombre, alias, cuenta_destino, relacion)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("ana", nombre, alias, cuenta_destino, relacion),
        )

    conn.execute(
        "INSERT INTO usuarios (account_id, username, password_hash, nombre) VALUES (?, ?, ?, ?)",
        ("luis", "luis", hash_password("pass456"), "Luis Peña"),
    )
    conn.execute(
        "INSERT INTO cuentas (account_id, numero_cuenta, saldo, moneda) VALUES (?, ?, ?, ?)",
        ("luis", "003344", 8200.00, "MXN"),
    )

    conn.commit()


def autenticar(conn: sqlite3.Connection, username: str, password: str) -> str | None:
    row = conn.execute(
        "SELECT account_id, password_hash FROM usuarios WHERE username = ?",
        (username,),
    ).fetchone()
    if row is None:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return row["account_id"]
