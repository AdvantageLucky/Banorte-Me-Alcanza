# Canal separado de agregados — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** El LLM deja de ver movimientos individuales (fecha/concepto/monto) y solo ve agregados por categoría; el detalle crudo sigue disponible exclusivamente vía `GET /api/movimientos` (REST directo, ya construido, sin cambios).

**Architecture:** Columna `categoria` nueva en `movimientos` (migración segura), asignada por código en las 2 funciones que insertan movimientos. Nueva tool MCP `get_resumen_movimientos` que agrupa por categoría. El LLM pierde acceso a `get_movimientos` (que sigue existiendo para el REST endpoint) y gana acceso a la nueva tool de agregados.

**Tech Stack:** Mismo stack existente — SQLite, `mcp`, `google-genai`. Sin dependencias nuevas.

**Spec:** `docs/superpowers/specs/2026-09-12-resumen-movimientos-design.md`

## Global Constraints

- `categoria` se asigna SIEMPRE por código (parámetro explícito de la función que inserta), nunca por parseo de `concepto`.
- Las únicas 3 categorías válidas hoy: `transferencia_enviada`, `transferencia_recibida`, `ahorro`. Default de la columna: `otro` (red de seguridad, no debería ocurrir con el código actual).
- La migración de schema debe ser segura de correr repetidamente y sobre una DB que ya tiene datos (no solo sobre una DB nueva).
- `GET /api/movimientos` (REST) y la tool MCP `get_movimientos` NO se tocan — siguen existiendo tal cual, sirven al canal directo REST.
- `get_movimientos` sale de `_READ_ONLY_TOOLS`/`read_only_tool_declarations()` en `orchestrator.py` — el LLM ya no puede llamarla.
- TDD en todo. Sin cambios a `frontend/`/`flutter_app/`. Sin atribución IA en commits.

---

### Task 1: `db.py` — columna `categoria`, migración, categorización por código, agregados

**Files:**
- Modify: `src/me_alcanza/mcp_bank/db.py`
- Test: `tests/mcp_bank/test_db.py`

**Interfaces:**
- Consumes: nada nuevo.
- Produces: `ejecutar_transferencia(...)` y `crear_apartado(...)` sin cambio de firma pública (la categoría se decide internamente, no es un parámetro nuevo del llamador); `get_resumen_movimientos(conn, account_id, fecha_inicio, fecha_fin) -> list[dict]` — consumido por Task 2.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/mcp_bank/test_db.py`:

```python
def test_migracion_categoria_es_idempotente(conn):
    # Correr get_connection otra vez (como pasaría en un segundo arranque del
    # proceso) no debe fallar aunque la columna ya exista.
    db.get_connection(":memory:")
    columnas = [row["name"] for row in conn.execute("PRAGMA table_info(movimientos)")]
    assert "categoria" in columnas


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
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_db.py -k "categoria or resumen_movimientos" -v`
Expected: FAIL — la columna no existe, `get_resumen_movimientos` no existe.

- [ ] **Step 3: Implementar en `src/me_alcanza/mcp_bank/db.py`**

3a. En `get_connection`, después de `conn.executescript(SCHEMA)` y antes del `return conn`:

```python
def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    try:
        conn.execute("ALTER TABLE movimientos ADD COLUMN categoria TEXT NOT NULL DEFAULT 'otro'")
    except sqlite3.OperationalError:
        pass  # la columna ya existe (DB migrada en un arranque anterior)
    return conn
```

3b. En `ejecutar_transferencia`, cambiar los dos `INSERT INTO movimientos` para incluir `categoria`:

```python
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
```

3c. En `crear_apartado`, cambiar el `INSERT INTO movimientos`:

```python
    conn.execute(
        "INSERT INTO movimientos (account_id, fecha, concepto, monto, categoria) VALUES (?, ?, ?, ?, ?)",
        (account_id, fecha_inicio, "Apartado de ahorro", -monto_por_periodo, "ahorro"),
    )
```

3d. Agregar al final del archivo:

```python
def get_resumen_movimientos(
    conn: sqlite3.Connection, account_id: str, fecha_inicio: str, fecha_fin: str
) -> list[dict]:
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
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_db.py -v`
Expected: PASS — todos, incluyendo los 6 nuevos.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/mcp_bank/db.py tests/mcp_bank/test_db.py
git commit -m "feat: add categoria column and get_resumen_movimientos aggregate query"
```

---

### Task 2: `server.py` — exponer `get_resumen_movimientos` vía MCP

**Files:**
- Modify: `src/me_alcanza/mcp_bank/server.py`
- Test: `tests/mcp_bank/test_server.py`

**Interfaces:**
- Consumes: `db.get_resumen_movimientos` (Task 1).
- Produces: tool MCP `get_resumen_movimientos` — consumida por Task 3.

- [ ] **Step 1: Actualizar el test del set exacto de tools (falla primero)**

En `tests/mcp_bank/test_server.py`, en `test_mcp_server_expone_las_tools_esperadas`, agregar `"get_resumen_movimientos"` al set esperado (junto a las 26 ya existentes — ahora son 27).

Agregar también, al final del archivo:

```python
@pytest.mark.asyncio
async def test_mcp_server_get_resumen_movimientos(tmp_path):
    from datetime import date

    db_path = tmp_path / "test_banco.db"
    async with stdio_client(_params(db_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await _call(
                session,
                "ejecutar_transferencia",
                {"origen_id": "luis", "destino_cuenta": "999999", "monto": 50.0, "concepto": "x"},
            )
            hoy = date.today().isoformat()
            resumen = await _call(
                session, "get_resumen_movimientos", {"account_id": "luis", "fecha_inicio": hoy, "fecha_fin": hoy}
            )
            assert resumen == [{"categoria": "transferencia_enviada", "total": -50.0, "count": 1}]
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_server.py -v`
Expected: FAIL — el tool-set no incluye la tool nueva, `test_mcp_server_get_resumen_movimientos` falla con "Unknown tool".

- [ ] **Step 3: Implementar en `src/me_alcanza/mcp_bank/server.py`**

Agregar, junto al import existente `from mcp.server.mcpserver.exceptions import ToolError`, y al final del archivo (antes de `if __name__ == "__main__":`):

```python
@mcp.tool()
def get_resumen_movimientos(account_id: str, fecha_inicio: str, fecha_fin: str) -> list[dict]:
    """Devuelve el total y conteo de movimientos agrupados por categoría dentro de un rango de fechas."""
    conn = _connection()
    try:
        return db.get_resumen_movimientos(conn, account_id, fecha_inicio, fecha_fin)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    finally:
        conn.close()
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_server.py -v`
Expected: PASS — todos, incluyendo el tool-set actualizado y el test nuevo.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/mcp_bank/server.py tests/mcp_bank/test_server.py
git commit -m "feat: expose get_resumen_movimientos via MCP server"
```

---

### Task 3: `orchestrator.py` — el LLM deja de ver movimientos individuales

**Files:**
- Modify: `src/me_alcanza/backend/orchestrator.py`
- Test: `tests/backend/test_orchestrator.py`

**Interfaces:**
- Consumes: tool MCP `get_resumen_movimientos` (Task 2).
- Produces: catálogo de tools del LLM actualizado.

- [ ] **Step 1: Escribir los tests que fallan, y limpiar los 2 tests existentes que quedan obsoletos**

Hay dos lugares en `tests/backend/test_orchestrator.py` que hoy dependen de que
el LLM pueda llamar `get_movimientos` directamente — con este cambio dejan de
ser válidos:

1. **Eliminar por completo** la función `test_handle_message_get_movimientos_reenvia_limit`
   (busca `async def test_handle_message_get_movimientos_reenvia_limit`) — su
   propósito (probar el round-trip de una tool que devuelve una lista) ya
   queda cubierto por el test nuevo `test_handle_message_get_resumen_movimientos_reenvia_fechas`
   de este mismo Step 1.
2. En `test_read_only_tool_declarations_expone_exactamente_las_herramientas_permitidas`,
   dentro del `assert names == {...}`, reemplazar la línea `"get_movimientos",`
   por `"get_resumen_movimientos",` (mismo lugar en el set, solo cambia el string).

Agregar al final de `tests/backend/test_orchestrator.py`:

```python
def test_get_movimientos_ya_no_esta_en_read_only_tools():
    from me_alcanza.backend.orchestrator import _READ_ONLY_TOOLS

    assert "get_movimientos" not in _READ_ONLY_TOOLS
    assert "get_resumen_movimientos" in _READ_ONLY_TOOLS


@pytest.mark.asyncio
async def test_handle_message_get_resumen_movimientos_reenvia_fechas():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(return_value=[{"categoria": "ahorro", "total": -100.0, "count": 2}])
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response(
                "get_resumen_movimientos", {"fecha_inicio": "2026-09-01", "fecha_fin": "2026-09-30"}
            ),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", "¿en qué gasté este mes?")

    mcp_client.call.assert_awaited_once_with(
        "get_resumen_movimientos",
        {"account_id": "ana", "fecha_inicio": "2026-09-01", "fecha_fin": "2026-09-30"},
    )
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/backend/test_orchestrator.py::test_get_movimientos_ya_no_esta_en_read_only_tools tests/backend/test_orchestrator.py::test_handle_message_get_resumen_movimientos_reenvia_fechas -v`
Expected: FAIL — `get_movimientos` sigue en el set, `get_resumen_movimientos` no existe.

- [ ] **Step 3: Implementar en `src/me_alcanza/backend/orchestrator.py`**

3a. En `_READ_ONLY_TOOLS`, quitar `"get_movimientos"` y agregar `"get_resumen_movimientos"`:

```python
_READ_ONLY_TOOLS = {
    "get_saldo",
    "get_cuenta",
    "get_resumen_movimientos",
    "get_ingresos_programados",
    "get_gastos_fijos",
    "get_metas",
    "buscar_contacto",
    "simular_flujo_de_caja",
}
```

3b. En `read_only_tool_declarations()`, reemplazar el bloque de la `FunctionDeclaration` de `get_movimientos` (la que tiene `"limit"` como propiedad) por:

```python
                types.FunctionDeclaration(
                    name="get_resumen_movimientos",
                    description=(
                        "Obtiene el total y conteo de movimientos de la cuenta del usuario actual, "
                        "agrupados por categoría, dentro de un rango de fechas. Úsala para responder "
                        "preguntas sobre patrones de gasto (ej. '¿en qué gasté este mes?'); nunca "
                        "pidas el detalle de movimientos individuales."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "fecha_inicio": types.Schema(
                                type=types.Type.STRING, description="Formato YYYY-MM-DD."
                            ),
                            "fecha_fin": types.Schema(
                                type=types.Type.STRING, description="Formato YYYY-MM-DD."
                            ),
                        },
                        required=["fecha_inicio", "fecha_fin"],
                    ),
                ),
```

3c. En `_dispatch_tool_call`, dentro del bloque `if call.name in _READ_ONLY_TOOLS:`, quitar la rama `if call.name == "get_movimientos" and call.args and "limit" in call.args: ...` y agregar:

```python
            elif call.name == "get_resumen_movimientos":
                call_args = call.args or {}
                fecha_inicio = call_args.get("fecha_inicio")
                fecha_fin = call_args.get("fecha_fin")
                if fecha_inicio is None:
                    return {"error": "Falta el argumento requerido: fecha_inicio"}
                if fecha_fin is None:
                    return {"error": "Falta el argumento requerido: fecha_fin"}
                args["fecha_inicio"] = fecha_inicio
                args["fecha_fin"] = fecha_fin
```

(Nota: la primera rama del `if/elif` sigue siendo `if call.name == "get_movimientos" ...` para `buscar_contacto` y `simular_flujo_de_caja` — solo quita la que compara contra `"get_movimientos"`, deja las demás intactas y agrega esta nueva como una rama `elif` más de la misma cadena.)

3d. En `build_system_prompt()`, dentro de `workflow_description`, agregar al final (antes del `)` que cierra la cadena):

```python
            "Para preguntas sobre patrones de gasto (ej. '¿en qué gasté este mes?', '¿cuánto gasté en "
            "transferencias?'), usa 'get_resumen_movimientos' calculando tú mismo el rango de fechas a "
            "partir de hoy (ej. 'este mes' = del día 1 del mes actual a hoy); nunca pidas ni inventes "
            "el detalle de movimientos individuales."
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/backend/test_orchestrator.py -v`
Expected: PASS — todos, incluyendo los 2 nuevos y con el test eliminado/actualizado del Step 1.

- [ ] **Step 5: Correr toda la suite**

Run: `uv run pytest tests/ -v`
Expected: PASS — todos los tests del proyecto.

- [ ] **Step 6: Commit**

```bash
git add src/me_alcanza/backend/orchestrator.py tests/backend/test_orchestrator.py
git commit -m "feat: replace get_movimientos with get_resumen_movimientos in LLM tool catalog"
```
