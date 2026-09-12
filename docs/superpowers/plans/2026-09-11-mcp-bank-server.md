# Servidor MCP "core-bancario" — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el servidor MCP "core-bancario" de `me-alcanza`: dueño único de la base de datos SQLite (usuarios, cuentas, movimientos, ingresos programados, gastos fijos, metas, apartados, contactos), con sus tools de lectura, la simulación determinista de flujo de caja, y las tools de mutación (transferencia, apartado).

**Architecture:** Un paquete Python (`me_alcanza.mcp_bank`) con tres módulos: `db.py` (esquema SQLite + CRUD + mutaciones, sin conocimiento de MCP), `cashflow.py` (función pura de proyección de flujo de caja, sin tocar la DB), y `server.py` (expone todo lo anterior como tools MCP vía stdio, usando el SDK `mcp`). Se construye de abajo hacia arriba: esquema+seed → tools de lectura → simulación → tools de mutación → wiring del servidor. Cada pieza tiene sus tests antes de pasar a la siguiente.

**Tech Stack:** Python ≥3.14, `uv`, `sqlite3` (stdlib), `hashlib`/`hmac` (stdlib, para hash de contraseñas — se usa PBKDF2-HMAC en vez de `bcrypt` para evitar una dependencia compilada el día del hackathon), SDK `mcp` (`mcp.server.mcpserver.MCPServer`), pytest.

**Spec:** `docs/superpowers/specs/2026-09-11-me-alcanza-design.md`

## Global Constraints

- `requires-python = ">=3.14"`.
- Todas las tools del MCP reciben `account_id` explícito como parámetro; este servidor no sabe nada de JWTs ni de sesiones (eso lo maneja el backend, en un plan posterior).
- Las funciones de `db.py` devuelven `None` cuando el recurso no existe (no lanzan excepción) para lecturas; `server.py` es quien decide convertir `None` en un error de MCP. Las mutaciones (`ejecutar_transferencia`, `crear_apartado`) sí lanzan `ValueError` directamente ante datos inválidos (monto ≤ 0, saldo insuficiente, cuenta/meta inexistente) — igual que en la prueba anterior.
- `simular_flujo_de_caja` vive en `cashflow.py`, es una función pura (no toca la DB, no usa `datetime.now()` internamente — recibe `hoy` como parámetro) para que sea 100% determinista y fácil de testear.
- Passwords se guardan con hash (`hash_password`/`verify_password` en `db.py`), nunca en texto plano — a diferencia de la prueba anterior.
- Contraseñas de los usuarios demo: `ana`/`pass123`, `luis`/`pass456` (mismas credenciales que la prueba anterior, para no reentrenar al equipo).

---

### Task 1: Scaffold del proyecto

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `src/me_alcanza/__init__.py`
- Create: `src/me_alcanza/mcp_bank/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/mcp_bank/__init__.py`

**Interfaces:**
- Produces: estructura de paquete `me_alcanza.mcp_bank` importable, entorno `uv` funcional.

- [ ] **Step 1: Crear `pyproject.toml`**

```toml
[project]
name = "me-alcanza"
version = "0.1.0"
description = "Asistente de flujo de caja con UI generativa (HackMTY 2026)"
requires-python = ">=3.14"
dependencies = [
    "a2ui-agent-sdk>=0.6.0",
    "fastapi>=0.141.1",
    "google-genai>=2.23.0",
    "mcp>=2.2.0",
    "pyjwt>=2.13.0",
    "python-dotenv>=1.2.3",
    "uvicorn>=0.52.4",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0"]

[build-system]
requires = ["uv_build>=0.12.10,<0.13.0"]
build-backend = "uv_build"

[dependency-groups]
dev = [
    "pytest-asyncio>=1.4.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Crear `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.env
*.db
```

- [ ] **Step 3: Crear `.env.example`**

```
GOOGLE_AI_STUDIO_API_KEY=
GEMINI_MODEL=
JWT_SECRET=cambia-esto-en-produccion
BANK_DB_PATH=banco.db
```

- [ ] **Step 4: Crear los `__init__.py` vacíos**

`src/me_alcanza/__init__.py`, `src/me_alcanza/mcp_bank/__init__.py`,
`tests/__init__.py`, `tests/mcp_bank/__init__.py` — los cuatro vacíos.

- [ ] **Step 5: Instalar dependencias y verificar el entorno**

Run: `uv sync --dev`
Expected: termina sin errores, crea `.venv/` y `uv.lock`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore .env.example src/ tests/ uv.lock
git commit -m "chore: scaffold proyecto me-alcanza"
```

---

### Task 2: Esquema, conexión, seed y autenticación

**Files:**
- Create: `src/me_alcanza/mcp_bank/db.py`
- Test: `tests/mcp_bank/test_db.py`

**Interfaces:**
- Consumes: nada (primera pieza de lógica real).
- Produces: `db.get_connection(db_path: str) -> sqlite3.Connection`,
  `db.seed(conn) -> None`, `db.hash_password(password: str) -> str`,
  `db.verify_password(password: str, password_hash: str) -> bool`,
  `db.autenticar(conn, username: str, password: str) -> str | None`
  (devuelve `account_id`). Usuarios seed: `account_id="ana"` (saldo
  500.00) y `account_id="luis"` (saldo 8200.00).

- [ ] **Step 1: Escribir tests de hash de contraseña y autenticación**

```python
# tests/mcp_bank/test_db.py
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
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError` o `AttributeError` (el módulo `db` no existe todavía).

- [ ] **Step 3: Implementar `db.py` (esquema, hash, seed, autenticar)**

```python
# src/me_alcanza/mcp_bank/db.py
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
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_db.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/mcp_bank/db.py tests/mcp_bank/test_db.py
git commit -m "feat: add banking DB schema, seed data and password auth"
```

---

### Task 3: Tools de lectura (saldo, cuenta, movimientos, ingresos, gastos, metas, contactos)

**Files:**
- Modify: `src/me_alcanza/mcp_bank/db.py`
- Modify: `tests/mcp_bank/test_db.py`

**Interfaces:**
- Consumes: `db.get_connection`, `db.seed` (Task 2).
- Produces: `db.get_saldo(conn, account_id) -> dict | None`,
  `db.get_cuenta(conn, account_id) -> dict | None`,
  `db.get_movimientos(conn, account_id, limit=10) -> list[dict]`,
  `db.get_ingresos_programados(conn, account_id) -> list[dict]`,
  `db.get_gastos_fijos(conn, account_id) -> list[dict]`,
  `db.get_metas(conn, account_id) -> list[dict]`,
  `db.buscar_contacto(conn, account_id, query: str) -> list[dict]`.

- [ ] **Step 1: Escribir tests de las tools de lectura**

```python
# agregar a tests/mcp_bank/test_db.py

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
    assert ingresos[0]["proxima_fecha"] == "2026-09-12"


def test_get_gastos_fijos(conn):
    gastos = db.get_gastos_fijos(conn, "ana")
    assert len(gastos) == 4
    conceptos = {g["concepto"] for g in gastos}
    assert conceptos == {"Agua", "Luz", "Colegiatura hijo 1", "Colegiatura hijo 2"}


def test_get_metas(conn):
    metas = db.get_metas(conn, "ana")
    assert len(metas) == 1
    assert metas[0]["monto_objetivo"] == 8000.00
    assert metas[0]["fecha_objetivo"] == "2026-10-13"
    assert metas[0]["monto_ahorrado"] == 0


def test_buscar_contacto_por_alias_ambiguo(conn):
    resultados = db.buscar_contacto(conn, "ana", "pepe")
    assert len(resultados) == 2
    relaciones = {r["relacion"] for r in resultados}
    assert relaciones == {"hermano", "primo"}


def test_buscar_contacto_sin_resultados(conn):
    assert db.buscar_contacto(conn, "ana", "nadie-existe") == []
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_db.py -v`
Expected: FAIL en los 9 tests nuevos — `AttributeError: module 'db' has no attribute 'get_saldo'`.

- [ ] **Step 3: Implementar las tools de lectura en `db.py`**

```python
# agregar a src/me_alcanza/mcp_bank/db.py

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


def get_gastos_fijos(conn: sqlite3.Connection, account_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, concepto, monto, frecuencia, proxima_fecha
        FROM gastos_fijos WHERE account_id = ?
        """,
        (account_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_metas(conn: sqlite3.Connection, account_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, descripcion, monto_objetivo, fecha_objetivo, monto_ahorrado
        FROM metas WHERE account_id = ?
        """,
        (account_id,),
    ).fetchall()
    return [dict(r) for r in rows]


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
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_db.py -v`
Expected: PASS (15 tests en total).

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/mcp_bank/db.py tests/mcp_bank/test_db.py
git commit -m "feat: add read tools for income, bills, goals and contacts"
```

---

### Task 4: Simulación determinista de flujo de caja

**Files:**
- Create: `src/me_alcanza/mcp_bank/cashflow.py`
- Create: `tests/mcp_bank/test_cashflow.py`

**Interfaces:**
- Consumes: nada (función pura, no toca la DB — recibe listas de dicts
  con la misma forma que devuelven `db.get_ingresos_programados` y
  `db.get_gastos_fijos`).
- Produces: `cashflow.simular_flujo_de_caja(saldo_actual: float,
  ingresos: list[dict], gastos: list[dict], hoy: str,
  fecha_objetivo: str, monto_objetivo: float) -> dict` con las llaves
  `alcanza: bool`, `saldo_minimo_proyectado: float`,
  `fecha_critica: str | None`, `margen: float`,
  `apartado_sugerido: dict | None` (con `monto_por_periodo`,
  `periodicidad`, `num_periodos` cuando `alcanza` es `False`).

- [ ] **Step 1: Escribir los tests de la simulación**

```python
# tests/mcp_bank/test_cashflow.py
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
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_cashflow.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'me_alcanza.mcp_bank.cashflow'`.

- [ ] **Step 3: Implementar `cashflow.py`**

```python
# src/me_alcanza/mcp_bank/cashflow.py
from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class _Evento:
    fecha: date
    monto: float  # positivo = ingreso, negativo = gasto


def _parse_fecha(fecha_str: str) -> date:
    return datetime.strptime(fecha_str, "%Y-%m-%d").date()


def simular_flujo_de_caja(
    saldo_actual: float,
    ingresos: list[dict],
    gastos: list[dict],
    hoy: str,
    fecha_objetivo: str,
    monto_objetivo: float,
) -> dict:
    hoy_fecha = _parse_fecha(hoy)
    objetivo = _parse_fecha(fecha_objetivo)
    if objetivo < hoy_fecha:
        raise ValueError("fecha_objetivo no puede ser anterior a hoy")

    eventos = [
        _Evento(_parse_fecha(i["proxima_fecha"]), i["monto"]) for i in ingresos
    ] + [
        _Evento(_parse_fecha(g["proxima_fecha"]), -g["monto"]) for g in gastos
    ]
    eventos = [e for e in eventos if hoy_fecha <= e.fecha <= objetivo]
    eventos.sort(key=lambda e: (e.fecha, 0 if e.monto >= 0 else 1))

    running = saldo_actual
    minimo = saldo_actual
    fecha_critica: date | None = None

    for evento in eventos:
        running += evento.monto
        if running < minimo:
            minimo = running
            fecha_critica = evento.fecha

    running -= monto_objetivo
    if running < minimo:
        minimo = running
        fecha_critica = objetivo

    alcanza = minimo >= 0
    margen = round(minimo, 2)

    apartado_sugerido = None
    if not alcanza:
        dias = max((objetivo - hoy_fecha).days, 1)
        num_periodos = max(dias // 7, 1)
        deficit = -minimo
        monto_por_periodo = round(deficit / num_periodos, 2)
        apartado_sugerido = {
            "monto_por_periodo": monto_por_periodo,
            "periodicidad": "semanal",
            "num_periodos": num_periodos,
        }

    return {
        "alcanza": alcanza,
        "saldo_minimo_proyectado": margen,
        "fecha_critica": fecha_critica.isoformat() if fecha_critica else None,
        "margen": margen,
        "apartado_sugerido": apartado_sugerido,
    }
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_cashflow.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/mcp_bank/cashflow.py tests/mcp_bank/test_cashflow.py
git commit -m "feat: add deterministic cashflow simulation"
```

---

### Task 5: Tools de mutación (transferencia, apartado)

**Files:**
- Modify: `src/me_alcanza/mcp_bank/db.py`
- Modify: `tests/mcp_bank/test_db.py`

**Interfaces:**
- Consumes: tablas `cuentas`, `movimientos`, `metas`, `apartados`
  (Task 2).
- Produces: `db.ejecutar_transferencia(conn, origen_id, destino_cuenta,
  monto, concepto) -> dict` (`{"ok": True, "nuevo_saldo": float,
  "movimiento": dict}`, lanza `ValueError` en monto ≤0, cuenta
  inexistente o saldo insuficiente), `db.crear_apartado(conn, account_id,
  meta_id, monto_por_periodo, periodicidad) -> dict` (`{"ok": True,
  "apartado": dict}`, lanza `ValueError` en meta inexistente/ajena o
  saldo insuficiente para el primer periodo).

- [ ] **Step 1: Escribir los tests de mutación**

```python
# agregar a tests/mcp_bank/test_db.py

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
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_db.py -v`
Expected: FAIL en los 7 tests nuevos — `AttributeError: module 'db' has no attribute 'ejecutar_transferencia'`.

- [ ] **Step 3: Implementar las tools de mutación en `db.py`**

```python
# agregar a src/me_alcanza/mcp_bank/db.py

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
        "INSERT INTO movimientos (account_id, fecha, concepto, monto) VALUES (?, ?, ?, ?)",
        (origen_id, fecha, concepto, -monto),
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
            "INSERT INTO movimientos (account_id, fecha, concepto, monto) VALUES (?, ?, ?, ?)",
            (destino["account_id"], fecha, f"Transferencia recibida: {concepto}", monto),
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
        "INSERT INTO movimientos (account_id, fecha, concepto, monto) VALUES (?, ?, ?, ?)",
        (account_id, fecha_inicio, "Apartado de ahorro", -monto_por_periodo),
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
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_db.py -v`
Expected: PASS (22 tests en total).

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/mcp_bank/db.py tests/mcp_bank/test_db.py
git commit -m "feat: add transfer and savings-pocket mutations"
```

---

### Task 6: Wiring del servidor MCP

**Files:**
- Create: `src/me_alcanza/mcp_bank/server.py`
- Create: `tests/mcp_bank/test_server.py`

**Interfaces:**
- Consumes: todo `db.py` (Tasks 2, 3, 5) y `cashflow.py` (Task 4).
- Produces: módulo ejecutable `me_alcanza.mcp_bank.server` (vía
  `python -m me_alcanza.mcp_bank.server`) que expone por stdio las tools:
  `autenticar`, `get_saldo`, `get_cuenta`, `get_movimientos`,
  `get_ingresos_programados`, `get_gastos_fijos`, `get_metas`,
  `buscar_contacto`, `simular_flujo_de_caja`, `ejecutar_transferencia`,
  `crear_apartado`. Un backend (plan posterior) se conecta a este
  servidor como subproceso stdio.

- [ ] **Step 1: Escribir los tests del servidor sobre stdio real**

Patrón verificado (ya usado y funcionando en
`prueba-ui-generativa/tests/mcp_bank/test_server.py`): se levanta el
servidor como subproceso real por `stdio_client` y se habla con él vía
`ClientSession`, en vez de llamar las funciones decoradas directamente
(la forma exacta en que `MCPServer.tool()` envuelve la función no está
garantizada entre versiones del SDK; el contrato estable es el protocolo
MCP en sí).

```python
# tests/mcp_bank/test_server.py
import json
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _params(db_path) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "me_alcanza.mcp_bank.server"],
        env={"BANK_DB_PATH": str(db_path)},
    )


async def _call(session: ClientSession, name: str, args: dict):
    result = await session.call_tool(name, args)
    text = result.content[0].text
    if result.is_error:
        raise RuntimeError(text)
    return json.loads(text)


@pytest.mark.asyncio
async def test_mcp_server_expone_las_tools_esperadas(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with stdio_client(_params(db_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert names == {
                "autenticar",
                "get_saldo",
                "get_cuenta",
                "get_movimientos",
                "get_ingresos_programados",
                "get_gastos_fijos",
                "get_metas",
                "buscar_contacto",
                "simular_flujo_de_caja",
                "ejecutar_transferencia",
                "crear_apartado",
            }


@pytest.mark.asyncio
async def test_mcp_server_flujo_de_caja_y_apartado(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with stdio_client(_params(db_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            account_id = await _call(session, "autenticar", {"username": "ana", "password": "pass123"})
            assert account_id == "ana"

            saldo = await _call(session, "get_saldo", {"account_id": "ana"})
            assert saldo == {"saldo": 500.00, "moneda": "MXN"}

            simulacion = await _call(
                session,
                "simular_flujo_de_caja",
                {"account_id": "ana", "fecha_objetivo": "2026-10-13", "monto_objetivo": 8000.0},
            )
            assert simulacion["alcanza"] is False
            assert simulacion["apartado_sugerido"]["periodicidad"] == "semanal"

            metas = await _call(session, "get_metas", {"account_id": "ana"})
            meta_id = metas[0]["id"]

            apartado = await _call(
                session,
                "crear_apartado",
                {
                    "account_id": "ana",
                    "meta_id": meta_id,
                    "monto_por_periodo": 142.5,
                    "periodicidad": "semanal",
                },
            )
            assert apartado["ok"] is True

            saldo_actualizado = await _call(session, "get_saldo", {"account_id": "ana"})
            assert saldo_actualizado["saldo"] == pytest.approx(500.00 - 142.5)


@pytest.mark.asyncio
async def test_mcp_server_desambiguacion_de_contacto(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with stdio_client(_params(db_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            contactos = await _call(session, "buscar_contacto", {"account_id": "ana", "query": "pepe"})
            assert len(contactos) == 2


@pytest.mark.asyncio
async def test_mcp_server_reporta_error_para_cuenta_inexistente(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with stdio_client(_params(db_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("get_saldo", {"account_id": "fantasma"})
            assert result.is_error is True
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `uv run pytest tests/mcp_bank/test_server.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'me_alcanza.mcp_bank.server'`.

- [ ] **Step 3: Implementar `server.py`**

```python
# src/me_alcanza/mcp_bank/server.py
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
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_server.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Correr toda la suite del MCP y confirmar cero regresiones**

Run: `uv run pytest tests/mcp_bank/ -v`
Expected: PASS (todos los tests de `test_db.py`, `test_cashflow.py` y
`test_server.py`, sin fallos).

- [ ] **Step 6: Commit**

```bash
git add src/me_alcanza/mcp_bank/server.py tests/mcp_bank/test_server.py
git commit -m "feat: wire core-bancario MCP server over stdio"
```

---

## Qué sigue

Este plan entrega el MCP server completo y probado de forma aislada
(se puede correr con `uv run python -m me_alcanza.mcp_bank.server` y
hablarle por stdio). El siguiente plan (`docs/superpowers/plans/`,
pendiente de escribir) cubre el backend FastAPI: autenticación JWT,
orquestación LLM↔MCP con Gemini, el contrato genérico de
propuesta/confirmación, y las rutas `/api/login`, `/api/chat`,
`/api/confirm-action`. Después de eso, dos planes más para los
frontends (React y Flutter), cada uno consumiendo la misma API.
