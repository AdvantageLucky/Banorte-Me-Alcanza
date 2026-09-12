import os

from mcp.server.mcpserver import MCPServer

from . import cashflow, db

DB_PATH = os.environ.get("BANK_DB_PATH", "banco.db")

mcp = MCPServer("core-bancario")


def _connection():
    conn = db.get_connection(DB_PATH)
    db.seed(conn)
    return conn


@mcp.tool()
def autenticar(username: str, password: str) -> str | None:
    """Valida usuario y password, devuelve el account_id o None si son incorrectos."""
    conn = _connection()
    try:
        return db.autenticar(conn, username, password)
    finally:
        conn.close()


@mcp.tool()
def get_saldo(account_id: str) -> dict:
    """Devuelve el saldo y la moneda de una cuenta."""
    conn = _connection()
    try:
        resultado = db.get_saldo(conn, account_id)
        if resultado is None:
            raise ValueError(f"Cuenta no encontrada: {account_id}")
        return resultado
    finally:
        conn.close()


@mcp.tool()
def get_cuenta(account_id: str) -> dict:
    """Devuelve titular, número de cuenta, saldo y moneda de una cuenta."""
    conn = _connection()
    try:
        resultado = db.get_cuenta(conn, account_id)
        if resultado is None:
            raise ValueError(f"Cuenta no encontrada: {account_id}")
        return resultado
    finally:
        conn.close()


@mcp.tool()
def get_movimientos(account_id: str, limit: int = 10) -> list[dict]:
    """Devuelve los movimientos más recientes de una cuenta."""
    conn = _connection()
    try:
        return db.get_movimientos(conn, account_id, limit=limit)
    finally:
        conn.close()


@mcp.tool()
def get_ingresos_programados(account_id: str) -> list[dict]:
    """Devuelve los ingresos recurrentes programados de una cuenta."""
    conn = _connection()
    try:
        return db.get_ingresos_programados(conn, account_id)
    finally:
        conn.close()


@mcp.tool()
def get_gastos_fijos(account_id: str) -> list[dict]:
    """Devuelve los gastos fijos recurrentes de una cuenta."""
    conn = _connection()
    try:
        return db.get_gastos_fijos(conn, account_id)
    finally:
        conn.close()


@mcp.tool()
def get_metas(account_id: str) -> list[dict]:
    """Devuelve las metas de ahorro guardadas de una cuenta."""
    conn = _connection()
    try:
        return db.get_metas(conn, account_id)
    finally:
        conn.close()


@mcp.tool()
def buscar_contacto(account_id: str, query: str) -> list[dict]:
    """Busca contactos/beneficiarios por nombre o alias; puede regresar varios resultados ambiguos."""
    conn = _connection()
    try:
        return db.buscar_contacto(conn, account_id, query)
    finally:
        conn.close()


@mcp.tool()
def simular_flujo_de_caja(
    account_id: str, fecha_objetivo: str, monto_objetivo: float
) -> dict:
    """Proyecta el flujo de caja entre hoy y fecha_objetivo y determina si alcanza para monto_objetivo."""
    from datetime import date

    conn = _connection()
    try:
        ingresos = db.get_ingresos_programados(conn, account_id)
        gastos = db.get_gastos_fijos(conn, account_id)
        saldo = db.get_saldo(conn, account_id)
        if saldo is None:
            raise ValueError(f"Cuenta no encontrada: {account_id}")
        return cashflow.simular_flujo_de_caja(
            saldo_actual=saldo["saldo"],
            ingresos=ingresos,
            gastos=gastos,
            hoy=date.today().isoformat(),
            fecha_objetivo=fecha_objetivo,
            monto_objetivo=monto_objetivo,
        )
    finally:
        conn.close()


@mcp.tool()
def ejecutar_transferencia(
    origen_id: str, destino_cuenta: str, monto: float, concepto: str
) -> dict:
    """Ejecuta una transferencia real, descontando saldo de la cuenta origen."""
    conn = _connection()
    try:
        return db.ejecutar_transferencia(conn, origen_id, destino_cuenta, monto, concepto)
    finally:
        conn.close()


@mcp.tool()
def crear_apartado(
    account_id: str, meta_id: int, monto_por_periodo: float, periodicidad: str
) -> dict:
    """Crea un apartado de ahorro real hacia una meta, descontando el primer periodo del saldo."""
    conn = _connection()
    try:
        return db.crear_apartado(conn, account_id, meta_id, monto_por_periodo, periodicidad)
    finally:
        conn.close()


if __name__ == "__main__":
    mcp.run()
