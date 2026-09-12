import hashlib
import hmac
import json
import os
import sqlite3
from datetime import date, datetime, timedelta

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
CREATE TABLE IF NOT EXISTS sugerencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL REFERENCES usuarios(account_id),
    tipo TEXT NOT NULL,
    entidad_id TEXT NOT NULL,
    detalle TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'pendiente',
    created_at TEXT NOT NULL,
    resuelta_at TEXT
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
    try:
        conn.execute("ALTER TABLE movimientos ADD COLUMN categoria TEXT NOT NULL DEFAULT 'otro'")
    except sqlite3.OperationalError:
        pass  # la columna ya existe (DB migrada en un arranque anterior)
    return conn


def seed(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    if existing > 0:
        return

    hoy = date.today()

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
        ("ana", "Nómina", 12500.00, "quincenal", (hoy + timedelta(days=1)).isoformat()),
    )
    for concepto, monto, dias_offset in [
        ("Agua", 320.00, 3),
        ("Luz", 450.00, 3),
        ("Colegiatura hijo 1", 2400.00, 4),
        ("Colegiatura hijo 2", 2400.00, 4),
    ]:
        conn.execute(
            """
            INSERT INTO gastos_fijos (account_id, concepto, monto, frecuencia, proxima_fecha)
            VALUES (?, ?, ?, 'mensual', ?)
            """,
            ("ana", concepto, monto, (hoy + timedelta(days=dias_offset)).isoformat()),
        )
    conn.execute(
        """
        INSERT INTO metas (account_id, descripcion, monto_objetivo, fecha_objetivo)
        VALUES (?, ?, ?, ?)
        """,
        ("ana", "Concierto (boletos + viaje)", 8000.00, (hoy + timedelta(days=32)).isoformat()),
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


def get_saldo(conn: sqlite3.Connection, account_id: str) -> dict | None:
    row = conn.execute(
        "SELECT saldo, moneda FROM cuentas WHERE account_id = ?", (account_id,)
    ).fetchone()
    if row is None:
        return None
    return {"saldo": row["saldo"], "moneda": row["moneda"]}


def get_cuenta(conn: sqlite3.Connection, account_id: str) -> dict | None:
    row = conn.execute(
        """
        SELECT u.nombre AS titular, c.numero_cuenta, c.saldo, c.moneda
        FROM cuentas c JOIN usuarios u ON u.account_id = c.account_id
        WHERE c.account_id = ?
        """,
        (account_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def get_movimientos(conn: sqlite3.Connection, account_id: str, limit: int = 10) -> list[dict]:
    rows = conn.execute(
        "SELECT fecha, concepto, monto FROM movimientos WHERE account_id = ? ORDER BY fecha DESC LIMIT ?",
        (account_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_ingresos_programados(conn: sqlite3.Connection, account_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, descripcion, monto, frecuencia, proxima_fecha
        FROM ingresos_programados WHERE account_id = ?
        """,
        (account_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def crear_ingreso_programado(
    conn: sqlite3.Connection,
    account_id: str,
    descripcion: str,
    monto: float,
    frecuencia: str,
    proxima_fecha: str,
) -> dict:
    if monto <= 0:
        raise ValueError("monto debe ser mayor a cero")
    cursor = conn.execute(
        """
        INSERT INTO ingresos_programados (account_id, descripcion, monto, frecuencia, proxima_fecha)
        VALUES (?, ?, ?, ?, ?)
        """,
        (account_id, descripcion, monto, frecuencia, proxima_fecha),
    )
    conn.commit()
    return {
        "id": cursor.lastrowid,
        "descripcion": descripcion,
        "monto": monto,
        "frecuencia": frecuencia,
        "proxima_fecha": proxima_fecha,
    }


def _get_ingreso_programado(conn: sqlite3.Connection, account_id: str, ingreso_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT id, descripcion, monto, frecuencia, proxima_fecha
        FROM ingresos_programados WHERE id = ? AND account_id = ?
        """,
        (ingreso_id, account_id),
    ).fetchone()
    return dict(row) if row is not None else None


def actualizar_ingreso_programado(
    conn: sqlite3.Connection,
    account_id: str,
    ingreso_id: int,
    descripcion: str,
    monto: float,
    frecuencia: str,
    proxima_fecha: str,
) -> dict:
    if monto <= 0:
        raise ValueError("monto debe ser mayor a cero")
    if _get_ingreso_programado(conn, account_id, ingreso_id) is None:
        raise ValueError(f"Ingreso programado no encontrado para esta cuenta: {ingreso_id}")
    conn.execute(
        """
        UPDATE ingresos_programados SET descripcion = ?, monto = ?, frecuencia = ?, proxima_fecha = ?
        WHERE id = ? AND account_id = ?
        """,
        (descripcion, monto, frecuencia, proxima_fecha, ingreso_id, account_id),
    )
    conn.commit()
    return {
        "id": ingreso_id,
        "descripcion": descripcion,
        "monto": monto,
        "frecuencia": frecuencia,
        "proxima_fecha": proxima_fecha,
    }


def eliminar_ingreso_programado(conn: sqlite3.Connection, account_id: str, ingreso_id: int) -> None:
    if _get_ingreso_programado(conn, account_id, ingreso_id) is None:
        raise ValueError(f"Ingreso programado no encontrado para esta cuenta: {ingreso_id}")
    conn.execute(
        "DELETE FROM ingresos_programados WHERE id = ? AND account_id = ?",
        (ingreso_id, account_id),
    )
    conn.commit()


def get_gastos_fijos(conn: sqlite3.Connection, account_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, concepto, monto, frecuencia, proxima_fecha
        FROM gastos_fijos WHERE account_id = ?
        """,
        (account_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def crear_gasto_fijo(
    conn: sqlite3.Connection,
    account_id: str,
    concepto: str,
    monto: float,
    frecuencia: str,
    proxima_fecha: str,
) -> dict:
    if monto <= 0:
        raise ValueError("monto debe ser mayor a cero")
    cursor = conn.execute(
        """
        INSERT INTO gastos_fijos (account_id, concepto, monto, frecuencia, proxima_fecha)
        VALUES (?, ?, ?, ?, ?)
        """,
        (account_id, concepto, monto, frecuencia, proxima_fecha),
    )
    conn.commit()
    return {
        "id": cursor.lastrowid,
        "concepto": concepto,
        "monto": monto,
        "frecuencia": frecuencia,
        "proxima_fecha": proxima_fecha,
    }


def _get_gasto_fijo(conn: sqlite3.Connection, account_id: str, gasto_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT id, concepto, monto, frecuencia, proxima_fecha
        FROM gastos_fijos WHERE id = ? AND account_id = ?
        """,
        (gasto_id, account_id),
    ).fetchone()
    return dict(row) if row is not None else None


def actualizar_gasto_fijo(
    conn: sqlite3.Connection,
    account_id: str,
    gasto_id: int,
    concepto: str,
    monto: float,
    frecuencia: str,
    proxima_fecha: str,
) -> dict:
    if monto <= 0:
        raise ValueError("monto debe ser mayor a cero")
    if _get_gasto_fijo(conn, account_id, gasto_id) is None:
        raise ValueError(f"Gasto fijo no encontrado para esta cuenta: {gasto_id}")
    conn.execute(
        """
        UPDATE gastos_fijos SET concepto = ?, monto = ?, frecuencia = ?, proxima_fecha = ?
        WHERE id = ? AND account_id = ?
        """,
        (concepto, monto, frecuencia, proxima_fecha, gasto_id, account_id),
    )
    conn.commit()
    return {
        "id": gasto_id,
        "concepto": concepto,
        "monto": monto,
        "frecuencia": frecuencia,
        "proxima_fecha": proxima_fecha,
    }


def eliminar_gasto_fijo(conn: sqlite3.Connection, account_id: str, gasto_id: int) -> None:
    if _get_gasto_fijo(conn, account_id, gasto_id) is None:
        raise ValueError(f"Gasto fijo no encontrado para esta cuenta: {gasto_id}")
    conn.execute(
        "DELETE FROM gastos_fijos WHERE id = ? AND account_id = ?",
        (gasto_id, account_id),
    )
    conn.commit()


def get_metas(conn: sqlite3.Connection, account_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, descripcion, monto_objetivo, fecha_objetivo, monto_ahorrado
        FROM metas WHERE account_id = ?
        """,
        (account_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def crear_meta(
    conn: sqlite3.Connection,
    account_id: str,
    descripcion: str,
    monto_objetivo: float,
    fecha_objetivo: str,
) -> dict:
    if monto_objetivo <= 0:
        raise ValueError("monto_objetivo debe ser mayor a cero")
    cursor = conn.execute(
        """
        INSERT INTO metas (account_id, descripcion, monto_objetivo, fecha_objetivo)
        VALUES (?, ?, ?, ?)
        """,
        (account_id, descripcion, monto_objetivo, fecha_objetivo),
    )
    conn.commit()
    return {
        "id": cursor.lastrowid,
        "descripcion": descripcion,
        "monto_objetivo": monto_objetivo,
        "fecha_objetivo": fecha_objetivo,
        "monto_ahorrado": 0,
    }


def _get_meta(conn: sqlite3.Connection, account_id: str, meta_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT id, descripcion, monto_objetivo, fecha_objetivo, monto_ahorrado
        FROM metas WHERE id = ? AND account_id = ?
        """,
        (meta_id, account_id),
    ).fetchone()
    return dict(row) if row is not None else None


def actualizar_meta(
    conn: sqlite3.Connection,
    account_id: str,
    meta_id: int,
    descripcion: str,
    monto_objetivo: float,
    fecha_objetivo: str,
) -> dict:
    if monto_objetivo <= 0:
        raise ValueError("monto_objetivo debe ser mayor a cero")
    existente = _get_meta(conn, account_id, meta_id)
    if existente is None:
        raise ValueError(f"Meta no encontrada para esta cuenta: {meta_id}")
    conn.execute(
        "UPDATE metas SET descripcion = ?, monto_objetivo = ?, fecha_objetivo = ? WHERE id = ? AND account_id = ?",
        (descripcion, monto_objetivo, fecha_objetivo, meta_id, account_id),
    )
    conn.commit()
    return {
        "id": meta_id,
        "descripcion": descripcion,
        "monto_objetivo": monto_objetivo,
        "fecha_objetivo": fecha_objetivo,
        "monto_ahorrado": existente["monto_ahorrado"],
    }


def eliminar_meta(conn: sqlite3.Connection, account_id: str, meta_id: int) -> None:
    if _get_meta(conn, account_id, meta_id) is None:
        raise ValueError(f"Meta no encontrada para esta cuenta: {meta_id}")
    activos = conn.execute(
        "SELECT COUNT(*) FROM apartados WHERE meta_id = ? AND estado = 'activo'",
        (meta_id,),
    ).fetchone()[0]
    if activos > 0:
        raise ValueError(
            "No puedes borrar una meta con apartados activos; cancela los apartados primero"
        )
    conn.execute("DELETE FROM metas WHERE id = ? AND account_id = ?", (meta_id, account_id))
    conn.commit()


def buscar_contacto(conn: sqlite3.Connection, account_id: str, query: str) -> list[dict]:
    like = f"%{query.lower()}%"
    rows = conn.execute(
        """
        SELECT id, nombre, alias, cuenta_destino, relacion
        FROM contactos
        WHERE account_id_titular = ?
          AND (LOWER(nombre) LIKE ? OR LOWER(alias) LIKE ?)
        """,
        (account_id, like, like),
    ).fetchall()
    return [dict(r) for r in rows]


def get_contacto(conn: sqlite3.Connection, account_id: str, contacto_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT id, nombre, alias, cuenta_destino, relacion
        FROM contactos
        WHERE id = ? AND account_id_titular = ?
        """,
        (contacto_id, account_id),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def crear_contacto(
    conn: sqlite3.Connection,
    account_id: str,
    nombre: str,
    alias: str,
    cuenta_destino: str,
    relacion: str,
) -> dict:
    cursor = conn.execute(
        """
        INSERT INTO contactos (account_id_titular, nombre, alias, cuenta_destino, relacion)
        VALUES (?, ?, ?, ?, ?)
        """,
        (account_id, nombre, alias, cuenta_destino, relacion),
    )
    conn.commit()
    return {
        "id": cursor.lastrowid,
        "nombre": nombre,
        "alias": alias,
        "cuenta_destino": cuenta_destino,
        "relacion": relacion,
    }


def actualizar_contacto(
    conn: sqlite3.Connection,
    account_id: str,
    contacto_id: int,
    nombre: str,
    alias: str,
    cuenta_destino: str,
    relacion: str,
) -> dict:
    if get_contacto(conn, account_id, contacto_id) is None:
        raise ValueError(f"Contacto no encontrado para esta cuenta: {contacto_id}")
    conn.execute(
        """
        UPDATE contactos SET nombre = ?, alias = ?, cuenta_destino = ?, relacion = ?
        WHERE id = ? AND account_id_titular = ?
        """,
        (nombre, alias, cuenta_destino, relacion, contacto_id, account_id),
    )
    conn.commit()
    return {
        "id": contacto_id,
        "nombre": nombre,
        "alias": alias,
        "cuenta_destino": cuenta_destino,
        "relacion": relacion,
    }


def eliminar_contacto(conn: sqlite3.Connection, account_id: str, contacto_id: int) -> None:
    if get_contacto(conn, account_id, contacto_id) is None:
        raise ValueError(f"Contacto no encontrado para esta cuenta: {contacto_id}")
    conn.execute(
        "DELETE FROM contactos WHERE id = ? AND account_id_titular = ?",
        (contacto_id, account_id),
    )
    conn.commit()


def ejecutar_transferencia(
    conn: sqlite3.Connection,
    origen_id: str,
    destino_cuenta: str,
    monto: float,
    concepto: str,
) -> dict:
    if monto <= 0:
        raise ValueError("El monto debe ser mayor a cero")

    origen = conn.execute(
        "SELECT saldo FROM cuentas WHERE account_id = ?", (origen_id,)
    ).fetchone()
    if origen is None:
        raise ValueError(f"Cuenta origen no encontrada: {origen_id}")
    if origen["saldo"] < monto:
        raise ValueError("Saldo insuficiente")

    nuevo_saldo_origen = origen["saldo"] - monto
    fecha = datetime.now().strftime("%Y-%m-%d")

    conn.execute(
        "UPDATE cuentas SET saldo = ? WHERE account_id = ?",
        (nuevo_saldo_origen, origen_id),
    )
    conn.execute(
        "INSERT INTO movimientos (account_id, fecha, concepto, monto, categoria) VALUES (?, ?, ?, ?, ?)",
        (origen_id, fecha, concepto, -monto, "transferencia_enviada"),
    )

    destino = conn.execute(
        "SELECT account_id, saldo FROM cuentas WHERE numero_cuenta = ?", (destino_cuenta,)
    ).fetchone()
    if destino is not None:
        conn.execute(
            "UPDATE cuentas SET saldo = ? WHERE account_id = ?",
            (destino["saldo"] + monto, destino["account_id"]),
        )
        conn.execute(
            "INSERT INTO movimientos (account_id, fecha, concepto, monto, categoria) VALUES (?, ?, ?, ?, ?)",
            (destino["account_id"], fecha, f"Transferencia recibida: {concepto}", monto, "transferencia_recibida"),
        )

    conn.commit()
    return {
        "ok": True,
        "nuevo_saldo": nuevo_saldo_origen,
        "movimiento": {"fecha": fecha, "concepto": concepto, "monto": -monto},
    }


def crear_apartado(
    conn: sqlite3.Connection,
    account_id: str,
    meta_id: int,
    monto_por_periodo: float,
    periodicidad: str,
) -> dict:
    if monto_por_periodo <= 0:
        raise ValueError("monto_por_periodo debe ser mayor a cero")

    meta = conn.execute(
        "SELECT id FROM metas WHERE id = ? AND account_id = ?", (meta_id, account_id)
    ).fetchone()
    if meta is None:
        raise ValueError(f"Meta no encontrada para esta cuenta: {meta_id}")

    cuenta = conn.execute(
        "SELECT saldo FROM cuentas WHERE account_id = ?", (account_id,)
    ).fetchone()
    if cuenta is None:
        raise ValueError(f"Cuenta no encontrada: {account_id}")
    if cuenta["saldo"] < monto_por_periodo:
        raise ValueError("Saldo insuficiente para el primer periodo del apartado")

    fecha_inicio = datetime.now().strftime("%Y-%m-%d")

    conn.execute(
        "UPDATE cuentas SET saldo = saldo - ? WHERE account_id = ?",
        (monto_por_periodo, account_id),
    )
    conn.execute(
        "UPDATE metas SET monto_ahorrado = monto_ahorrado + ? WHERE id = ?",
        (monto_por_periodo, meta_id),
    )
    cursor = conn.execute(
        """
        INSERT INTO apartados (account_id, meta_id, monto_por_periodo, periodicidad, fecha_inicio, estado)
        VALUES (?, ?, ?, ?, ?, 'activo')
        """,
        (account_id, meta_id, monto_por_periodo, periodicidad, fecha_inicio),
    )
    conn.execute(
        "INSERT INTO movimientos (account_id, fecha, concepto, monto, categoria) VALUES (?, ?, ?, ?, ?)",
        (account_id, fecha_inicio, "Apartado de ahorro", -monto_por_periodo, "ahorro"),
    )
    conn.commit()

    return {
        "ok": True,
        "apartado": {
            "id": cursor.lastrowid,
            "meta_id": meta_id,
            "monto_por_periodo": monto_por_periodo,
            "periodicidad": periodicidad,
            "fecha_inicio": fecha_inicio,
            "estado": "activo",
        },
    }


def listar_apartados(conn: sqlite3.Connection, account_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, meta_id, monto_por_periodo, periodicidad, fecha_inicio, estado
        FROM apartados WHERE account_id = ?
        """,
        (account_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def cancelar_apartado(conn: sqlite3.Connection, account_id: str, apartado_id: int) -> dict:
    row = conn.execute(
        """
        SELECT id, meta_id, monto_por_periodo, periodicidad, fecha_inicio, estado
        FROM apartados WHERE id = ? AND account_id = ?
        """,
        (apartado_id, account_id),
    ).fetchone()
    if row is None:
        raise ValueError(f"Apartado no encontrado para esta cuenta: {apartado_id}")
    conn.execute(
        "UPDATE apartados SET estado = 'cancelado' WHERE id = ? AND account_id = ?",
        (apartado_id, account_id),
    )
    conn.commit()
    resultado = dict(row)
    resultado["estado"] = "cancelado"
    return resultado


def get_resumen_movimientos(
    conn: sqlite3.Connection, account_id: str, fecha_inicio: str, fecha_fin: str
) -> list[dict]:
    for nombre, valor in (("fecha_inicio", fecha_inicio), ("fecha_fin", fecha_fin)):
        try:
            date.fromisoformat(valor)
        except ValueError as exc:
            raise ValueError(f"{nombre} debe tener formato YYYY-MM-DD, recibido: {valor!r}") from exc
    rows = conn.execute(
        """
        SELECT categoria, SUM(monto) AS total, COUNT(*) AS count
        FROM movimientos
        WHERE account_id = ? AND fecha >= ? AND fecha <= ?
        GROUP BY categoria
        """,
        (account_id, fecha_inicio, fecha_fin),
    ).fetchall()
    return [dict(r) for r in rows]


_ESTADOS_VALIDOS_SUGERENCIA = {"pendiente", "atendida", "descartada"}


def crear_sugerencia(
    conn: sqlite3.Connection, account_id: str, tipo: str, entidad_id: str, detalle: dict
) -> dict:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.execute(
        """
        INSERT INTO sugerencias (account_id, tipo, entidad_id, detalle, estado, created_at)
        VALUES (?, ?, ?, ?, 'pendiente', ?)
        """,
        (account_id, tipo, entidad_id, json.dumps(detalle), created_at),
    )
    conn.commit()
    return {
        "id": cursor.lastrowid,
        "tipo": tipo,
        "entidad_id": entidad_id,
        "detalle": detalle,
        "estado": "pendiente",
        "created_at": created_at,
        "resuelta_at": None,
    }


def existe_sugerencia_pendiente(conn: sqlite3.Connection, account_id: str, tipo: str, entidad_id: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM sugerencias
        WHERE account_id = ? AND tipo = ? AND entidad_id = ? AND estado = 'pendiente'
        """,
        (account_id, tipo, entidad_id),
    ).fetchone()
    return row is not None


def listar_sugerencias(conn: sqlite3.Connection, account_id: str, estado: str | None = None) -> list[dict]:
    if estado is not None:
        rows = conn.execute(
            """
            SELECT id, tipo, entidad_id, detalle, estado, created_at, resuelta_at
            FROM sugerencias WHERE account_id = ? AND estado = ?
            ORDER BY created_at DESC
            """,
            (account_id, estado),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, tipo, entidad_id, detalle, estado, created_at, resuelta_at
            FROM sugerencias WHERE account_id = ?
            ORDER BY created_at DESC
            """,
            (account_id,),
        ).fetchall()
    resultado = []
    for row in rows:
        item = dict(row)
        item["detalle"] = json.loads(item["detalle"])
        resultado.append(item)
    return resultado


def marcar_sugerencia(conn: sqlite3.Connection, account_id: str, sugerencia_id: int, nuevo_estado: str) -> dict:
    if nuevo_estado not in _ESTADOS_VALIDOS_SUGERENCIA - {"pendiente"}:
        raise ValueError(f"Estado inválido para marcar una sugerencia: {nuevo_estado}")
    row = conn.execute(
        "SELECT id FROM sugerencias WHERE id = ? AND account_id = ?", (sugerencia_id, account_id)
    ).fetchone()
    if row is None:
        raise ValueError(f"Sugerencia no encontrada para esta cuenta: {sugerencia_id}")
    resuelta_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE sugerencias SET estado = ?, resuelta_at = ? WHERE id = ? AND account_id = ?",
        (nuevo_estado, resuelta_at, sugerencia_id, account_id),
    )
    conn.commit()
    actualizada = conn.execute(
        "SELECT id, tipo, entidad_id, detalle, estado, created_at, resuelta_at FROM sugerencias WHERE id = ?",
        (sugerencia_id,),
    ).fetchone()
    resultado = dict(actualizada)
    resultado["detalle"] = json.loads(resultado["detalle"])
    return resultado
