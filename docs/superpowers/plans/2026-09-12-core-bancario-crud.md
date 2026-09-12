# CRUD del core bancario simulado — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar CRUD real (endpoints REST + DTOs + lógica) sobre contactos, ingresos programados, gastos fijos, metas y apartados del core bancario simulado, más la capacidad del LLM de proponer (nunca ejecutar directo) la creación de estas entidades por chat.

**Architecture:** Bottom-up: primero las funciones de `db.py` (SQLite), luego las tools de `server.py` (MCP) que las envuelven, luego los DTOs de Pydantic, luego las rutas REST que llaman las tools MCP directo (sin LLM), y al final el flujo conversacional (`proponer_X` + ramas de `confirm_action`) que reutiliza las mismas tools de creación.

**Tech Stack:** FastAPI, Pydantic, SQLite (`sqlite3` stdlib), MCP (`mcp` SDK), `google-genai`. Mismo stack que el backend existente, sin dependencias nuevas.

**Spec:** `docs/superpowers/specs/2026-09-12-core-bancario-crud-design.md`

## Global Constraints

- Ninguna tool nueva se agrega a `_READ_ONLY_TOOLS` ni a `read_only_tool_declarations()` salvo las 4 `proponer_X` explícitas (`proponer_contacto`, `proponer_gasto_fijo`, `proponer_ingreso_programado`, `proponer_meta`) — el LLM nunca ve ni puede llamar las tools de `actualizar_X`/`eliminar_X`/`cancelar_apartado`/`listar_apartados` directamente.
- Toda operación de update/delete/cancelar valida ownership (`account_id` del JWT) antes de tocar el registro — `ValueError` si no pertenece a la cuenta o no existe.
- Manejo de errores uniforme: cualquier `RuntimeError` que llegue desde `BankMcpClient.call` en una ruta nueva se traduce a `HTTPException(status_code=400, detail=str(exc))`.
- `metas.monto_ahorrado` nunca es parte de un DTO de create/update — siempre derivado (solo cambia vía `crear_apartado`).
- Borrar una meta con algún apartado `estado='activo'` apuntándole: bloqueado (`ValueError` → 400).
- Fechas en DTOs usan el tipo `date` de Pydantic; al llamar una tool MCP (que espera `str` ISO) siempre se convierte con `str(valor)` — funciona igual para un `date` recién parseado que para un string ISO que ya traía un registro existente.
- `frecuencia`/`periodicidad` en los DTOs: `Literal["semanal", "quincenal", "mensual", "anual"]`. La columna SQL sigue siendo `TEXT`, sin migración.
- Chat (LLM): solo puede **proponer creación** de contactos/gastos fijos/ingresos programados/metas (mismo patrón de `proponer_transferencia`/`proponer_apartado`: nunca ejecuta directo, siempre vía `confirm_action` tras confirmación explícita del usuario). Editar/borrar estas entidades es exclusivo de REST — nunca por chat.
- TDD en todo: test primero, verlo fallar, implementar mínimo, verlo pasar, commit.
- Sin cambios a `frontend/` ni `flutter_app/` en este plan (sub-proyecto backend-only).
- Nunca agregar atribución a IA/Claude/Anthropic en ningún commit.

---

### Task 1: `db.py` — CRUD de contactos

**Files:**
- Modify: `src/me_alcanza/mcp_bank/db.py`
- Test: `tests/mcp_bank/test_db.py`

**Interfaces:**
- Consumes: `get_contacto(conn, account_id, contacto_id)` (ya existe, línea ~250) para verificar ownership.
- Produces: `crear_contacto(conn, account_id, nombre, alias, cuenta_destino, relacion) -> dict`, `actualizar_contacto(conn, account_id, contacto_id, nombre, alias, cuenta_destino, relacion) -> dict`, `eliminar_contacto(conn, account_id, contacto_id) -> None` — consumidos por Task 6 (server.py).

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/mcp_bank/test_db.py`:

```python
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
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_db.py -k contacto -v`
Expected: FAIL — `AttributeError: module 'db' has no attribute 'crear_contacto'`.

- [ ] **Step 3: Implementar en `src/me_alcanza/mcp_bank/db.py`**

Agregar después de `get_contacto` (línea ~261):

```python
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
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_db.py -v`
Expected: PASS — todos los tests, incluyendo los 6 nuevos.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/mcp_bank/db.py tests/mcp_bank/test_db.py
git commit -m "feat: add contacto CRUD to db layer"
```

---

### Task 2: `db.py` — CRUD de ingresos programados

**Files:**
- Modify: `src/me_alcanza/mcp_bank/db.py`
- Test: `tests/mcp_bank/test_db.py`

**Interfaces:**
- Produces: `crear_ingreso_programado(conn, account_id, descripcion, monto, frecuencia, proxima_fecha) -> dict`, `actualizar_ingreso_programado(conn, account_id, ingreso_id, descripcion, monto, frecuencia, proxima_fecha) -> dict`, `eliminar_ingreso_programado(conn, account_id, ingreso_id) -> None` — consumidos por Task 6.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/mcp_bank/test_db.py`:

```python
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
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_db.py -k ingreso_programado -v`
Expected: FAIL — `AttributeError`.

- [ ] **Step 3: Implementar en `src/me_alcanza/mcp_bank/db.py`**

Agregar después de `get_ingresos_programados` (línea ~211):

```python
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
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_db.py -v`
Expected: PASS — todos.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/mcp_bank/db.py tests/mcp_bank/test_db.py
git commit -m "feat: add ingreso_programado CRUD to db layer"
```

---

### Task 3: `db.py` — CRUD de gastos fijos

**Files:**
- Modify: `src/me_alcanza/mcp_bank/db.py`
- Test: `tests/mcp_bank/test_db.py`

**Interfaces:**
- Produces: `crear_gasto_fijo(conn, account_id, concepto, monto, frecuencia, proxima_fecha) -> dict`, `actualizar_gasto_fijo(conn, account_id, gasto_id, concepto, monto, frecuencia, proxima_fecha) -> dict`, `eliminar_gasto_fijo(conn, account_id, gasto_id) -> None` — consumidos por Task 6.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/mcp_bank/test_db.py`:

```python
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
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_db.py -k gasto_fijo -v`
Expected: FAIL — `AttributeError`.

- [ ] **Step 3: Implementar en `src/me_alcanza/mcp_bank/db.py`**

Agregar después de `get_gastos_fijos` (línea ~222):

```python
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
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_db.py -v`
Expected: PASS — todos.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/mcp_bank/db.py tests/mcp_bank/test_db.py
git commit -m "feat: add gasto_fijo CRUD to db layer"
```

---

### Task 4: `db.py` — CRUD de metas (con bloqueo por apartados activos)

**Files:**
- Modify: `src/me_alcanza/mcp_bank/db.py`
- Test: `tests/mcp_bank/test_db.py`

**Interfaces:**
- Produces: `crear_meta(conn, account_id, descripcion, monto_objetivo, fecha_objetivo) -> dict`, `actualizar_meta(conn, account_id, meta_id, descripcion, monto_objetivo, fecha_objetivo) -> dict`, `eliminar_meta(conn, account_id, meta_id) -> None` — consumidos por Task 6. `eliminar_meta` lee la tabla `apartados` directamente (ya existe en el schema).

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/mcp_bank/test_db.py`:

```python
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
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_db.py -k meta -v`
Expected: FAIL — `AttributeError`.

- [ ] **Step 3: Implementar en `src/me_alcanza/mcp_bank/db.py`**

Agregar después de `get_metas` (línea ~233):

```python
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
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_db.py -v`
Expected: PASS — todos.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/mcp_bank/db.py tests/mcp_bank/test_db.py
git commit -m "feat: add meta CRUD to db layer, block delete with active apartados"
```

---

### Task 5: `db.py` — listar y cancelar apartados

**Files:**
- Modify: `src/me_alcanza/mcp_bank/db.py`
- Test: `tests/mcp_bank/test_db.py`

**Interfaces:**
- Produces: `listar_apartados(conn, account_id) -> list[dict]`, `cancelar_apartado(conn, account_id, apartado_id) -> dict` — consumidos por Task 6.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/mcp_bank/test_db.py`:

```python
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
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_db.py -k apartado -v`
Expected: FAIL en los 5 nuevos — `AttributeError`.

- [ ] **Step 3: Implementar en `src/me_alcanza/mcp_bank/db.py`**

Agregar al final del archivo (después de `crear_apartado`):

```python
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
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_db.py -v`
Expected: PASS — todos.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/mcp_bank/db.py tests/mcp_bank/test_db.py
git commit -m "feat: add listar/cancelar apartados to db layer"
```

---

### Task 6: `server.py` — exponer las 14 tools MCP nuevas

**Files:**
- Modify: `src/me_alcanza/mcp_bank/server.py`
- Test: `tests/mcp_bank/test_server.py`

**Interfaces:**
- Consumes: todas las funciones de `db.py` de las Tasks 1-5.
- Produces: 14 tools MCP nuevas — consumidas por Task 7 (DTOs no dependen de esto, pero rutas y orquestador sí): `crear_contacto`, `actualizar_contacto`, `eliminar_contacto`, `crear_ingreso_programado`, `actualizar_ingreso_programado`, `eliminar_ingreso_programado`, `crear_gasto_fijo`, `actualizar_gasto_fijo`, `eliminar_gasto_fijo`, `crear_meta`, `actualizar_meta`, `eliminar_meta`, `listar_apartados`, `cancelar_apartado`.

- [ ] **Step 1: Actualizar el test de la lista exacta de tools (falla primero)**

En `tests/mcp_bank/test_server.py`, reemplazar el `assert names == {...}` dentro de `test_mcp_server_expone_las_tools_esperadas` por:

```python
            assert names == {
                "autenticar",
                "get_saldo",
                "get_cuenta",
                "get_movimientos",
                "get_ingresos_programados",
                "get_gastos_fijos",
                "get_metas",
                "buscar_contacto",
                "get_contacto",
                "simular_flujo_de_caja",
                "ejecutar_transferencia",
                "crear_apartado",
                "crear_contacto",
                "actualizar_contacto",
                "eliminar_contacto",
                "crear_ingreso_programado",
                "actualizar_ingreso_programado",
                "eliminar_ingreso_programado",
                "crear_gasto_fijo",
                "actualizar_gasto_fijo",
                "eliminar_gasto_fijo",
                "crear_meta",
                "actualizar_meta",
                "eliminar_meta",
                "listar_apartados",
                "cancelar_apartado",
            }
```

También agregar, al final de `tests/mcp_bank/test_server.py`, dos tests de integración representativos (no hace falta repetir los 14 uno por uno vía stdio, ya están cubiertos a fondo en `test_db.py`; aquí solo se verifica que el envoltorio MCP funciona):

```python
@pytest.mark.asyncio
async def test_mcp_server_crear_y_eliminar_contacto(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with stdio_client(_params(db_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            contacto = await _call(
                session,
                "crear_contacto",
                {
                    "account_id": "ana",
                    "nombre": "Sofía López",
                    "alias": "Sofi",
                    "cuenta_destino": "5566778899",
                    "relacion": "amiga",
                },
            )
            assert contacto["nombre"] == "Sofía López"

            resultado = await _call(
                session, "eliminar_contacto", {"account_id": "ana", "contacto_id": contacto["id"]}
            )
            assert resultado["ok"] is True


@pytest.mark.asyncio
async def test_mcp_server_eliminar_meta_con_apartado_activo_reporta_error(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with stdio_client(_params(db_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            metas = await _call(session, "get_metas", {"account_id": "ana"})
            meta_id = metas[0]["id"]
            await _call(
                session,
                "crear_apartado",
                {"account_id": "ana", "meta_id": meta_id, "monto_por_periodo": 50.0, "periodicidad": "semanal"},
            )
            result = await session.call_tool("eliminar_meta", {"account_id": "ana", "meta_id": meta_id})
            assert result.is_error is True
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_server.py -v`
Expected: FAIL — el test de tool-set falla (faltan 14 tools), los 2 tests nuevos fallan (`Unknown tool`).

- [ ] **Step 3: Implementar en `src/me_alcanza/mcp_bank/server.py`**

Agregar al final del archivo, antes de `if __name__ == "__main__":`:

```python
@mcp.tool()
def crear_contacto(account_id: str, nombre: str, alias: str, cuenta_destino: str, relacion: str) -> dict:
    """Crea un contacto/beneficiario nuevo para la cuenta del usuario."""
    conn = _connection()
    try:
        return db.crear_contacto(conn, account_id, nombre, alias, cuenta_destino, relacion)
    finally:
        conn.close()


@mcp.tool()
def actualizar_contacto(
    account_id: str, contacto_id: int, nombre: str, alias: str, cuenta_destino: str, relacion: str
) -> dict:
    """Actualiza un contacto existente de la cuenta del usuario."""
    conn = _connection()
    try:
        return db.actualizar_contacto(conn, account_id, contacto_id, nombre, alias, cuenta_destino, relacion)
    finally:
        conn.close()


@mcp.tool()
def eliminar_contacto(account_id: str, contacto_id: int) -> dict:
    """Elimina un contacto de la cuenta del usuario."""
    conn = _connection()
    try:
        db.eliminar_contacto(conn, account_id, contacto_id)
        return {"ok": True}
    finally:
        conn.close()


@mcp.tool()
def crear_ingreso_programado(
    account_id: str, descripcion: str, monto: float, frecuencia: str, proxima_fecha: str
) -> dict:
    """Crea un ingreso recurrente programado nuevo para la cuenta del usuario."""
    conn = _connection()
    try:
        return db.crear_ingreso_programado(conn, account_id, descripcion, monto, frecuencia, proxima_fecha)
    finally:
        conn.close()


@mcp.tool()
def actualizar_ingreso_programado(
    account_id: str,
    ingreso_id: int,
    descripcion: str,
    monto: float,
    frecuencia: str,
    proxima_fecha: str,
) -> dict:
    """Actualiza un ingreso programado existente de la cuenta del usuario."""
    conn = _connection()
    try:
        return db.actualizar_ingreso_programado(
            conn, account_id, ingreso_id, descripcion, monto, frecuencia, proxima_fecha
        )
    finally:
        conn.close()


@mcp.tool()
def eliminar_ingreso_programado(account_id: str, ingreso_id: int) -> dict:
    """Elimina un ingreso programado de la cuenta del usuario."""
    conn = _connection()
    try:
        db.eliminar_ingreso_programado(conn, account_id, ingreso_id)
        return {"ok": True}
    finally:
        conn.close()


@mcp.tool()
def crear_gasto_fijo(account_id: str, concepto: str, monto: float, frecuencia: str, proxima_fecha: str) -> dict:
    """Crea un gasto fijo recurrente nuevo para la cuenta del usuario."""
    conn = _connection()
    try:
        return db.crear_gasto_fijo(conn, account_id, concepto, monto, frecuencia, proxima_fecha)
    finally:
        conn.close()


@mcp.tool()
def actualizar_gasto_fijo(
    account_id: str, gasto_id: int, concepto: str, monto: float, frecuencia: str, proxima_fecha: str
) -> dict:
    """Actualiza un gasto fijo existente de la cuenta del usuario."""
    conn = _connection()
    try:
        return db.actualizar_gasto_fijo(conn, account_id, gasto_id, concepto, monto, frecuencia, proxima_fecha)
    finally:
        conn.close()


@mcp.tool()
def eliminar_gasto_fijo(account_id: str, gasto_id: int) -> dict:
    """Elimina un gasto fijo de la cuenta del usuario."""
    conn = _connection()
    try:
        db.eliminar_gasto_fijo(conn, account_id, gasto_id)
        return {"ok": True}
    finally:
        conn.close()


@mcp.tool()
def crear_meta(account_id: str, descripcion: str, monto_objetivo: float, fecha_objetivo: str) -> dict:
    """Crea una meta de ahorro nueva para la cuenta del usuario."""
    conn = _connection()
    try:
        return db.crear_meta(conn, account_id, descripcion, monto_objetivo, fecha_objetivo)
    finally:
        conn.close()


@mcp.tool()
def actualizar_meta(
    account_id: str, meta_id: int, descripcion: str, monto_objetivo: float, fecha_objetivo: str
) -> dict:
    """Actualiza una meta de ahorro existente de la cuenta del usuario."""
    conn = _connection()
    try:
        return db.actualizar_meta(conn, account_id, meta_id, descripcion, monto_objetivo, fecha_objetivo)
    finally:
        conn.close()


@mcp.tool()
def eliminar_meta(account_id: str, meta_id: int) -> dict:
    """Elimina una meta de ahorro de la cuenta del usuario. Falla si tiene apartados activos."""
    conn = _connection()
    try:
        db.eliminar_meta(conn, account_id, meta_id)
        return {"ok": True}
    finally:
        conn.close()


@mcp.tool()
def listar_apartados(account_id: str) -> list[dict]:
    """Lista todos los apartados de ahorro (activos y cancelados) de la cuenta del usuario."""
    conn = _connection()
    try:
        return db.listar_apartados(conn, account_id)
    finally:
        conn.close()


@mcp.tool()
def cancelar_apartado(account_id: str, apartado_id: int) -> dict:
    """Cancela un apartado de ahorro activo de la cuenta del usuario."""
    conn = _connection()
    try:
        return db.cancelar_apartado(conn, account_id, apartado_id)
    finally:
        conn.close()
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_server.py -v`
Expected: PASS — todos, incluyendo el tool-set y los 2 tests de integración nuevos.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/mcp_bank/server.py tests/mcp_bank/test_server.py
git commit -m "feat: expose 14 new CRUD tools via MCP server"
```

---

### Task 7: DTOs nuevos

**Files:**
- Modify: `src/me_alcanza/backend/dtos.py`

**Interfaces:**
- Produces: `CuentaResponse`, `MovimientoResponse`, `ContactoCreate/Update/Response`, `IngresoProgramadoCreate/Update/Response`, `GastoFijoCreate/Update/Response`, `MetaCreate/Update/Response`, `ApartadoCreate/Response`, `Frecuencia` (type alias) — consumidos por Task 9-13 (rutas).

No hay tests automatizados para este task (son solo modelos Pydantic declarativos, sin lógica propia); se verifican indirectamente en las Tasks 9-13 cuando las rutas los usan. Verificación aquí: que el módulo importe sin errores.

- [ ] **Step 1: Implementar en `src/me_alcanza/backend/dtos.py`**

Agregar al inicio del archivo (después de los imports existentes de `pydantic`):

```python
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Frecuencia = Literal["semanal", "quincenal", "mensual", "anual"]
```

Agregar al final del archivo:

```python
class CuentaResponse(BaseModel):
    titular: str
    numero_cuenta: str
    saldo: float
    moneda: str


class MovimientoResponse(BaseModel):
    fecha: str
    concepto: str
    monto: float


class ContactoCreate(BaseModel):
    nombre: str
    alias: str
    cuenta_destino: str
    relacion: str


class ContactoUpdate(BaseModel):
    nombre: str | None = None
    alias: str | None = None
    cuenta_destino: str | None = None
    relacion: str | None = None


class ContactoResponse(BaseModel):
    id: int
    nombre: str
    alias: str
    cuenta_destino: str
    relacion: str


class IngresoProgramadoCreate(BaseModel):
    descripcion: str
    monto: float = Field(gt=0)
    frecuencia: Frecuencia
    proxima_fecha: date


class IngresoProgramadoUpdate(BaseModel):
    descripcion: str | None = None
    monto: float | None = Field(default=None, gt=0)
    frecuencia: Frecuencia | None = None
    proxima_fecha: date | None = None


class IngresoProgramadoResponse(BaseModel):
    id: int
    descripcion: str
    monto: float
    frecuencia: str
    proxima_fecha: str


class GastoFijoCreate(BaseModel):
    concepto: str
    monto: float = Field(gt=0)
    frecuencia: Frecuencia
    proxima_fecha: date


class GastoFijoUpdate(BaseModel):
    concepto: str | None = None
    monto: float | None = Field(default=None, gt=0)
    frecuencia: Frecuencia | None = None
    proxima_fecha: date | None = None


class GastoFijoResponse(BaseModel):
    id: int
    concepto: str
    monto: float
    frecuencia: str
    proxima_fecha: str


class MetaCreate(BaseModel):
    descripcion: str
    monto_objetivo: float = Field(gt=0)
    fecha_objetivo: date


class MetaUpdate(BaseModel):
    descripcion: str | None = None
    monto_objetivo: float | None = Field(default=None, gt=0)
    fecha_objetivo: date | None = None


class MetaResponse(BaseModel):
    id: int
    descripcion: str
    monto_objetivo: float
    fecha_objetivo: str
    monto_ahorrado: float


class ApartadoCreate(BaseModel):
    meta_id: int
    monto_por_periodo: float = Field(gt=0)
    periodicidad: Frecuencia


class ApartadoResponse(BaseModel):
    id: int
    meta_id: int
    monto_por_periodo: float
    periodicidad: str
    fecha_inicio: str
    estado: str
```

- [ ] **Step 2: Verificar que importa sin errores**

Run: `uv run python3 -c "from me_alcanza.backend import dtos"`
Expected: sin salida, sin excepción.

- [ ] **Step 3: Commit**

```bash
git add src/me_alcanza/backend/dtos.py
git commit -m "feat: add DTOs for core bancario CRUD entities"
```

---

### Task 8: Rutas REST — cuenta y movimientos (solo lectura)

**Files:**
- Modify: `src/me_alcanza/backend/routes.py`
- Test: `tests/backend/test_routes.py`

**Interfaces:**
- Consumes: `CuentaResponse`, `MovimientoResponse` (Task 7); tools MCP `get_cuenta`, `get_movimientos` (ya existentes).
- Produces: `GET /api/cuenta`, `GET /api/movimientos?limit=`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/backend/test_routes.py`:

```python
def _login(client) -> str:
    login = client.post("/api/login", json={"username": "ana", "password": "pass123"})
    return login.json()["token"]


def test_get_cuenta(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.get("/api/cuenta", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        body = response.json()
        assert body["numero_cuenta"] == "001122"
        assert body["saldo"] == 500.00


def test_get_cuenta_sin_token_devuelve_401(app):
    with TestClient(app) as client:
        response = client.get("/api/cuenta")
        assert response.status_code == 401


def test_get_movimientos_vacio(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.get("/api/movimientos", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json() == []


def test_get_movimientos_respeta_limit(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.get("/api/movimientos?limit=3", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/backend/test_routes.py -k "cuenta or movimientos" -v`
Expected: FAIL — 404 Not Found (rutas no existen).

- [ ] **Step 3: Implementar en `src/me_alcanza/backend/routes.py`**

Modificar el import de `.dtos` al inicio del archivo para incluir los DTOs nuevos:

```python
from .dtos import (
    ChatRequest,
    ChatResponse,
    ConfirmActionRequest,
    ConfirmActionResponse,
    CuentaResponse,
    LoginRequest,
    LoginResponse,
    MovimientoResponse,
)
```

Agregar al final del archivo:

```python
@router.get("/cuenta", response_model=CuentaResponse)
async def get_cuenta_route(
    request: Request, account_id: str = Depends(auth.get_current_account_id)
) -> CuentaResponse:
    try:
        cuenta = await request.app.state.mcp_client.call("get_cuenta", {"account_id": account_id})
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CuentaResponse(**cuenta)


@router.get("/movimientos", response_model=list[MovimientoResponse])
async def get_movimientos_route(
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
    limit: int = 10,
) -> list[MovimientoResponse]:
    movimientos = await request.app.state.mcp_client.call(
        "get_movimientos", {"account_id": account_id, "limit": limit}
    )
    return [MovimientoResponse(**m) for m in movimientos]
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/backend/test_routes.py -v`
Expected: PASS — todos.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/backend/routes.py tests/backend/test_routes.py
git commit -m "feat: add GET /api/cuenta and /api/movimientos routes"
```

---

### Task 9: Rutas REST — CRUD de contactos

**Files:**
- Modify: `src/me_alcanza/backend/routes.py`
- Test: `tests/backend/test_routes.py`

**Interfaces:**
- Consumes: `ContactoCreate/Update/Response` (Task 7); tools MCP `buscar_contacto`, `get_contacto` (existentes), `crear_contacto`/`actualizar_contacto`/`eliminar_contacto` (Task 6).
- Produces: `GET/POST /api/contactos`, `PATCH/DELETE /api/contactos/{contacto_id}`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/backend/test_routes.py`:

```python
def test_list_contactos(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.get("/api/contactos", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert len(response.json()) == 2


def test_create_contacto(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.post(
            "/api/contactos",
            json={"nombre": "Sofía López", "alias": "Sofi", "cuenta_destino": "5566778899", "relacion": "amiga"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.json()["nombre"] == "Sofía López"


def test_update_contacto(app):
    with TestClient(app) as client:
        token = _login(client)
        contacto_id = client.get("/api/contactos", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
        response = client.patch(
            f"/api/contactos/{contacto_id}",
            json={"alias": "Nuevo alias"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["alias"] == "Nuevo alias"


def test_update_contacto_inexistente_devuelve_400(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.patch(
            "/api/contactos/999999",
            json={"alias": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400


def test_delete_contacto(app):
    with TestClient(app) as client:
        token = _login(client)
        contacto_id = client.get("/api/contactos", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
        response = client.delete(
            f"/api/contactos/{contacto_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 204
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/backend/test_routes.py -k contacto -v`
Expected: FAIL — 404 Not Found.

- [ ] **Step 3: Implementar en `src/me_alcanza/backend/routes.py`**

Actualizar el import de `.dtos` para agregar los 3 DTOs de contacto:

```python
from .dtos import (
    ChatRequest,
    ChatResponse,
    ConfirmActionRequest,
    ConfirmActionResponse,
    ContactoCreate,
    ContactoResponse,
    ContactoUpdate,
    CuentaResponse,
    LoginRequest,
    LoginResponse,
    MovimientoResponse,
)
```

Agregar al final del archivo:

```python
@router.get("/contactos", response_model=list[ContactoResponse])
async def list_contactos(
    request: Request, account_id: str = Depends(auth.get_current_account_id)
) -> list[ContactoResponse]:
    contactos = await request.app.state.mcp_client.call(
        "buscar_contacto", {"account_id": account_id, "query": ""}
    )
    return [ContactoResponse(**c) for c in contactos]


@router.post("/contactos", response_model=ContactoResponse, status_code=201)
async def create_contacto(
    payload: ContactoCreate,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> ContactoResponse:
    contacto = await request.app.state.mcp_client.call(
        "crear_contacto",
        {
            "account_id": account_id,
            "nombre": payload.nombre,
            "alias": payload.alias,
            "cuenta_destino": payload.cuenta_destino,
            "relacion": payload.relacion,
        },
    )
    return ContactoResponse(**contacto)


@router.patch("/contactos/{contacto_id}", response_model=ContactoResponse)
async def update_contacto(
    contacto_id: int,
    payload: ContactoUpdate,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> ContactoResponse:
    try:
        actual = await request.app.state.mcp_client.call(
            "get_contacto", {"account_id": account_id, "contacto_id": contacto_id}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    merged = {**actual, **payload.model_dump(exclude_unset=True)}
    try:
        actualizado = await request.app.state.mcp_client.call(
            "actualizar_contacto",
            {
                "account_id": account_id,
                "contacto_id": contacto_id,
                "nombre": merged["nombre"],
                "alias": merged["alias"],
                "cuenta_destino": merged["cuenta_destino"],
                "relacion": merged["relacion"],
            },
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ContactoResponse(**actualizado)


@router.delete("/contactos/{contacto_id}", status_code=204)
async def delete_contacto(
    contacto_id: int,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> None:
    try:
        await request.app.state.mcp_client.call(
            "eliminar_contacto", {"account_id": account_id, "contacto_id": contacto_id}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/backend/test_routes.py -v`
Expected: PASS — todos.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/backend/routes.py tests/backend/test_routes.py
git commit -m "feat: add REST CRUD routes for contactos"
```

---

### Task 10: Rutas REST — CRUD de ingresos programados

**Files:**
- Modify: `src/me_alcanza/backend/routes.py`
- Test: `tests/backend/test_routes.py`

**Interfaces:**
- Consumes: `IngresoProgramadoCreate/Update/Response` (Task 7); tools MCP `get_ingresos_programados` (existente), `crear_ingreso_programado`/`actualizar_ingreso_programado`/`eliminar_ingreso_programado` (Task 6).
- Produces: `GET/POST /api/ingresos-programados`, `PATCH/DELETE /api/ingresos-programados/{ingreso_id}`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/backend/test_routes.py`:

```python
def test_list_ingresos_programados(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.get("/api/ingresos-programados", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert len(response.json()) == 1


def test_create_ingreso_programado(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.post(
            "/api/ingresos-programados",
            json={"descripcion": "Bono", "monto": 5000.0, "frecuencia": "anual", "proxima_fecha": "2026-12-01"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.json()["descripcion"] == "Bono"


def test_update_ingreso_programado_parcial(app):
    with TestClient(app) as client:
        token = _login(client)
        ingreso_id = client.get(
            "/api/ingresos-programados", headers={"Authorization": f"Bearer {token}"}
        ).json()[0]["id"]
        response = client.patch(
            f"/api/ingresos-programados/{ingreso_id}",
            json={"monto": 13000.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["monto"] == 13000.0
        assert response.json()["descripcion"] == "Nómina"


def test_delete_ingreso_programado(app):
    with TestClient(app) as client:
        token = _login(client)
        ingreso_id = client.get(
            "/api/ingresos-programados", headers={"Authorization": f"Bearer {token}"}
        ).json()[0]["id"]
        response = client.delete(
            f"/api/ingresos-programados/{ingreso_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 204
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/backend/test_routes.py -k ingreso_programado -v`
Expected: FAIL — 404 Not Found.

- [ ] **Step 3: Implementar en `src/me_alcanza/backend/routes.py`**

Actualizar el import de `.dtos` agregando `IngresoProgramadoCreate`, `IngresoProgramadoResponse`, `IngresoProgramadoUpdate`.

Agregar al final del archivo:

```python
@router.get("/ingresos-programados", response_model=list[IngresoProgramadoResponse])
async def list_ingresos_programados(
    request: Request, account_id: str = Depends(auth.get_current_account_id)
) -> list[IngresoProgramadoResponse]:
    ingresos = await request.app.state.mcp_client.call(
        "get_ingresos_programados", {"account_id": account_id}
    )
    return [IngresoProgramadoResponse(**i) for i in ingresos]


@router.post("/ingresos-programados", response_model=IngresoProgramadoResponse, status_code=201)
async def create_ingreso_programado(
    payload: IngresoProgramadoCreate,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> IngresoProgramadoResponse:
    ingreso = await request.app.state.mcp_client.call(
        "crear_ingreso_programado",
        {
            "account_id": account_id,
            "descripcion": payload.descripcion,
            "monto": payload.monto,
            "frecuencia": payload.frecuencia,
            "proxima_fecha": str(payload.proxima_fecha),
        },
    )
    return IngresoProgramadoResponse(**ingreso)


@router.patch("/ingresos-programados/{ingreso_id}", response_model=IngresoProgramadoResponse)
async def update_ingreso_programado(
    ingreso_id: int,
    payload: IngresoProgramadoUpdate,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> IngresoProgramadoResponse:
    ingresos = await request.app.state.mcp_client.call(
        "get_ingresos_programados", {"account_id": account_id}
    )
    actual = next((i for i in ingresos if i["id"] == ingreso_id), None)
    if actual is None:
        raise HTTPException(status_code=400, detail=f"Ingreso programado no encontrado para esta cuenta: {ingreso_id}")

    merged = {**actual, **payload.model_dump(exclude_unset=True)}
    try:
        actualizado = await request.app.state.mcp_client.call(
            "actualizar_ingreso_programado",
            {
                "account_id": account_id,
                "ingreso_id": ingreso_id,
                "descripcion": merged["descripcion"],
                "monto": merged["monto"],
                "frecuencia": merged["frecuencia"],
                "proxima_fecha": str(merged["proxima_fecha"]),
            },
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return IngresoProgramadoResponse(**actualizado)


@router.delete("/ingresos-programados/{ingreso_id}", status_code=204)
async def delete_ingreso_programado(
    ingreso_id: int,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> None:
    try:
        await request.app.state.mcp_client.call(
            "eliminar_ingreso_programado", {"account_id": account_id, "ingreso_id": ingreso_id}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/backend/test_routes.py -v`
Expected: PASS — todos.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/backend/routes.py tests/backend/test_routes.py
git commit -m "feat: add REST CRUD routes for ingresos programados"
```

---

### Task 11: Rutas REST — CRUD de gastos fijos

**Files:**
- Modify: `src/me_alcanza/backend/routes.py`
- Test: `tests/backend/test_routes.py`

**Interfaces:**
- Consumes: `GastoFijoCreate/Update/Response` (Task 7); tools MCP `get_gastos_fijos` (existente), `crear_gasto_fijo`/`actualizar_gasto_fijo`/`eliminar_gasto_fijo` (Task 6).
- Produces: `GET/POST /api/gastos-fijos`, `PATCH/DELETE /api/gastos-fijos/{gasto_id}`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/backend/test_routes.py`:

```python
def test_list_gastos_fijos(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.get("/api/gastos-fijos", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert len(response.json()) == 4


def test_create_gasto_fijo(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.post(
            "/api/gastos-fijos",
            json={"concepto": "Internet", "monto": 600.0, "frecuencia": "mensual", "proxima_fecha": "2026-10-05"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.json()["concepto"] == "Internet"


def test_update_gasto_fijo_parcial(app):
    with TestClient(app) as client:
        token = _login(client)
        gasto_id = client.get("/api/gastos-fijos", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
        response = client.patch(
            f"/api/gastos-fijos/{gasto_id}",
            json={"monto": 350.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["monto"] == 350.0


def test_delete_gasto_fijo(app):
    with TestClient(app) as client:
        token = _login(client)
        gasto_id = client.get("/api/gastos-fijos", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
        response = client.delete(f"/api/gastos-fijos/{gasto_id}", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 204
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/backend/test_routes.py -k gasto_fijo -v`
Expected: FAIL — 404 Not Found.

- [ ] **Step 3: Implementar en `src/me_alcanza/backend/routes.py`**

Actualizar el import de `.dtos` agregando `GastoFijoCreate`, `GastoFijoResponse`, `GastoFijoUpdate`.

Agregar al final del archivo:

```python
@router.get("/gastos-fijos", response_model=list[GastoFijoResponse])
async def list_gastos_fijos(
    request: Request, account_id: str = Depends(auth.get_current_account_id)
) -> list[GastoFijoResponse]:
    gastos = await request.app.state.mcp_client.call("get_gastos_fijos", {"account_id": account_id})
    return [GastoFijoResponse(**g) for g in gastos]


@router.post("/gastos-fijos", response_model=GastoFijoResponse, status_code=201)
async def create_gasto_fijo(
    payload: GastoFijoCreate,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> GastoFijoResponse:
    gasto = await request.app.state.mcp_client.call(
        "crear_gasto_fijo",
        {
            "account_id": account_id,
            "concepto": payload.concepto,
            "monto": payload.monto,
            "frecuencia": payload.frecuencia,
            "proxima_fecha": str(payload.proxima_fecha),
        },
    )
    return GastoFijoResponse(**gasto)


@router.patch("/gastos-fijos/{gasto_id}", response_model=GastoFijoResponse)
async def update_gasto_fijo(
    gasto_id: int,
    payload: GastoFijoUpdate,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> GastoFijoResponse:
    gastos = await request.app.state.mcp_client.call("get_gastos_fijos", {"account_id": account_id})
    actual = next((g for g in gastos if g["id"] == gasto_id), None)
    if actual is None:
        raise HTTPException(status_code=400, detail=f"Gasto fijo no encontrado para esta cuenta: {gasto_id}")

    merged = {**actual, **payload.model_dump(exclude_unset=True)}
    try:
        actualizado = await request.app.state.mcp_client.call(
            "actualizar_gasto_fijo",
            {
                "account_id": account_id,
                "gasto_id": gasto_id,
                "concepto": merged["concepto"],
                "monto": merged["monto"],
                "frecuencia": merged["frecuencia"],
                "proxima_fecha": str(merged["proxima_fecha"]),
            },
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GastoFijoResponse(**actualizado)


@router.delete("/gastos-fijos/{gasto_id}", status_code=204)
async def delete_gasto_fijo(
    gasto_id: int,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> None:
    try:
        await request.app.state.mcp_client.call(
            "eliminar_gasto_fijo", {"account_id": account_id, "gasto_id": gasto_id}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/backend/test_routes.py -v`
Expected: PASS — todos.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/backend/routes.py tests/backend/test_routes.py
git commit -m "feat: add REST CRUD routes for gastos fijos"
```

---

### Task 12: Rutas REST — CRUD de metas

**Files:**
- Modify: `src/me_alcanza/backend/routes.py`
- Test: `tests/backend/test_routes.py`

**Interfaces:**
- Consumes: `MetaCreate/Update/Response` (Task 7); tools MCP `get_metas` (existente), `crear_meta`/`actualizar_meta`/`eliminar_meta` (Task 6).
- Produces: `GET/POST /api/metas`, `PATCH/DELETE /api/metas/{meta_id}`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/backend/test_routes.py`:

```python
def test_list_metas(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.get("/api/metas", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert len(response.json()) == 1


def test_create_meta(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.post(
            "/api/metas",
            json={"descripcion": "Viaje", "monto_objetivo": 20000.0, "fecha_objetivo": "2027-01-01"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.json()["monto_ahorrado"] == 0


def test_update_meta_parcial(app):
    with TestClient(app) as client:
        token = _login(client)
        meta_id = client.get("/api/metas", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
        response = client.patch(
            f"/api/metas/{meta_id}",
            json={"monto_objetivo": 9000.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["monto_objetivo"] == 9000.0


def test_delete_meta_sin_apartados(app):
    with TestClient(app) as client:
        token = _login(client)
        crear = client.post(
            "/api/metas",
            json={"descripcion": "Borrable", "monto_objetivo": 1000.0, "fecha_objetivo": "2027-01-01"},
            headers={"Authorization": f"Bearer {token}"},
        )
        meta_id = crear.json()["id"]
        response = client.delete(f"/api/metas/{meta_id}", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 204


def test_delete_meta_con_apartado_activo_devuelve_400(app):
    with TestClient(app) as client:
        token = _login(client)
        meta_id = client.get("/api/metas", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
        client.post(
            "/api/apartados",
            json={"meta_id": meta_id, "monto_por_periodo": 50.0, "periodicidad": "semanal"},
            headers={"Authorization": f"Bearer {token}"},
        )
        response = client.delete(f"/api/metas/{meta_id}", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 400
```

Nota: `test_delete_meta_con_apartado_activo_devuelve_400` depende de `POST /api/apartados`, que se implementa en la Task 13 — este test queda pendiente (fallará con 404 en `/api/apartados`) hasta que esa task esté hecha. Es intencional: ambas tasks son parte del mismo sub-proyecto y se ejecutan en orden.

- [ ] **Step 2: Correr y verificar que fallan**

Nota: no usar `-k "meta and not apartado"` aquí — `test_delete_meta_sin_apartados` contiene la subcadena "apartado" en su nombre y quedaría excluido por accidente, aunque sí debe correr en esta task (no depende de `/api/apartados`, a diferencia de `test_delete_meta_con_apartado_activo_devuelve_400`). Seleccionar los 4 tests explícitamente:

Run: `uv run pytest tests/backend/test_routes.py::test_list_metas tests/backend/test_routes.py::test_create_meta tests/backend/test_routes.py::test_update_meta_parcial tests/backend/test_routes.py::test_delete_meta_sin_apartados -v`
Expected: FAIL — 404 Not Found (los 4 tests que no dependen de `/api/apartados`).

- [ ] **Step 3: Implementar en `src/me_alcanza/backend/routes.py`**

Actualizar el import de `.dtos` agregando `MetaCreate`, `MetaResponse`, `MetaUpdate`.

Agregar al final del archivo:

```python
@router.get("/metas", response_model=list[MetaResponse])
async def list_metas(
    request: Request, account_id: str = Depends(auth.get_current_account_id)
) -> list[MetaResponse]:
    metas = await request.app.state.mcp_client.call("get_metas", {"account_id": account_id})
    return [MetaResponse(**m) for m in metas]


@router.post("/metas", response_model=MetaResponse, status_code=201)
async def create_meta(
    payload: MetaCreate,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> MetaResponse:
    meta = await request.app.state.mcp_client.call(
        "crear_meta",
        {
            "account_id": account_id,
            "descripcion": payload.descripcion,
            "monto_objetivo": payload.monto_objetivo,
            "fecha_objetivo": str(payload.fecha_objetivo),
        },
    )
    return MetaResponse(**meta)


@router.patch("/metas/{meta_id}", response_model=MetaResponse)
async def update_meta(
    meta_id: int,
    payload: MetaUpdate,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> MetaResponse:
    metas = await request.app.state.mcp_client.call("get_metas", {"account_id": account_id})
    actual = next((m for m in metas if m["id"] == meta_id), None)
    if actual is None:
        raise HTTPException(status_code=400, detail=f"Meta no encontrada para esta cuenta: {meta_id}")

    merged = {**actual, **payload.model_dump(exclude_unset=True)}
    try:
        actualizada = await request.app.state.mcp_client.call(
            "actualizar_meta",
            {
                "account_id": account_id,
                "meta_id": meta_id,
                "descripcion": merged["descripcion"],
                "monto_objetivo": merged["monto_objetivo"],
                "fecha_objetivo": str(merged["fecha_objetivo"]),
            },
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MetaResponse(**actualizada)


@router.delete("/metas/{meta_id}", status_code=204)
async def delete_meta(
    meta_id: int,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> None:
    try:
        await request.app.state.mcp_client.call("eliminar_meta", {"account_id": account_id, "meta_id": meta_id})
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

- [ ] **Step 4: Correr y verificar que pasan (parcial)**

Run: `uv run pytest tests/backend/test_routes.py::test_list_metas tests/backend/test_routes.py::test_create_meta tests/backend/test_routes.py::test_update_meta_parcial tests/backend/test_routes.py::test_delete_meta_sin_apartados -v`
Expected: PASS — 4 tests.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/backend/routes.py tests/backend/test_routes.py
git commit -m "feat: add REST CRUD routes for metas"
```

---

### Task 13: Rutas REST — apartados (listar, crear, cancelar)

**Files:**
- Modify: `src/me_alcanza/backend/routes.py`
- Test: `tests/backend/test_routes.py`

**Interfaces:**
- Consumes: `ApartadoCreate/Response` (Task 7); tools MCP `crear_apartado` (existente), `listar_apartados`/`cancelar_apartado` (Task 6).
- Produces: `GET/POST /api/apartados`, `POST /api/apartados/{apartado_id}/cancelar`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/backend/test_routes.py`:

```python
def test_list_apartados_vacio(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.get("/api/apartados", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json() == []


def test_create_apartado(app):
    with TestClient(app) as client:
        token = _login(client)
        meta_id = client.get("/api/metas", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
        response = client.post(
            "/api/apartados",
            json={"meta_id": meta_id, "monto_por_periodo": 50.0, "periodicidad": "semanal"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.json()["estado"] == "activo"


def test_cancelar_apartado(app):
    with TestClient(app) as client:
        token = _login(client)
        meta_id = client.get("/api/metas", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
        apartado = client.post(
            "/api/apartados",
            json={"meta_id": meta_id, "monto_por_periodo": 50.0, "periodicidad": "semanal"},
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        response = client.post(
            f"/api/apartados/{apartado['id']}/cancelar", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["estado"] == "cancelado"


def test_cancelar_apartado_inexistente_devuelve_400(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.post("/api/apartados/999999/cancelar", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 400
```

- [ ] **Step 2: Correr y verificar que fallan**

Nota: no usar `-k apartado` aquí — matchearía también `test_delete_meta_sin_apartados` y `test_delete_meta_con_apartado_activo_devuelve_400` de la Task 12 (ya implementados), mezclando resultados. Seleccionar los 4 tests nuevos explícitamente:

Run: `uv run pytest tests/backend/test_routes.py::test_list_apartados_vacio tests/backend/test_routes.py::test_create_apartado tests/backend/test_routes.py::test_cancelar_apartado tests/backend/test_routes.py::test_cancelar_apartado_inexistente_devuelve_400 -v`
Expected: FAIL — 404 Not Found.

- [ ] **Step 3: Implementar en `src/me_alcanza/backend/routes.py`**

Actualizar el import de `.dtos` agregando `ApartadoCreate`, `ApartadoResponse`.

Agregar al final del archivo:

```python
@router.get("/apartados", response_model=list[ApartadoResponse])
async def list_apartados(
    request: Request, account_id: str = Depends(auth.get_current_account_id)
) -> list[ApartadoResponse]:
    apartados = await request.app.state.mcp_client.call("listar_apartados", {"account_id": account_id})
    return [ApartadoResponse(**a) for a in apartados]


@router.post("/apartados", response_model=ApartadoResponse, status_code=201)
async def create_apartado(
    payload: ApartadoCreate,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> ApartadoResponse:
    try:
        resultado = await request.app.state.mcp_client.call(
            "crear_apartado",
            {
                "account_id": account_id,
                "meta_id": payload.meta_id,
                "monto_por_periodo": payload.monto_por_periodo,
                "periodicidad": payload.periodicidad,
            },
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApartadoResponse(**resultado["apartado"])


@router.post("/apartados/{apartado_id}/cancelar", response_model=ApartadoResponse)
async def cancelar_apartado_route(
    apartado_id: int,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> ApartadoResponse:
    try:
        resultado = await request.app.state.mcp_client.call(
            "cancelar_apartado", {"account_id": account_id, "apartado_id": apartado_id}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApartadoResponse(**resultado)
```

- [ ] **Step 4: Correr y verificar que pasan (todo `test_routes.py`, incluyendo el test pendiente de la Task 12)**

Run: `uv run pytest tests/backend/test_routes.py -v`
Expected: PASS — todos, incluyendo ahora `test_delete_meta_con_apartado_activo_devuelve_400`.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/backend/routes.py tests/backend/test_routes.py
git commit -m "feat: add REST routes for apartados (listar, crear, cancelar)"
```

---

### Task 14: Flujo conversacional — `proponer_X` + `confirm_action` para las 4 entidades

**Files:**
- Modify: `src/me_alcanza/backend/orchestrator.py`
- Test: `tests/backend/test_orchestrator.py`

**Interfaces:**
- Consumes: tools MCP `crear_contacto`/`crear_gasto_fijo`/`crear_ingreso_programado`/`crear_meta` (Task 6); `proposals.crear_propuesta`/`obtener_propuesta_valida`/`descartar_propuesta` (ya existentes).
- Produces: 4 `FunctionDeclaration` nuevas, 4 métodos `_proponer_X`, 4 ramas nuevas en `_dispatch_tool_call` y en `confirm_action`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/backend/test_orchestrator.py`:

```python
@pytest.mark.asyncio
async def test_handle_message_proponer_contacto_crea_propuesta_sin_tocar_mcp():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock()
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response(
                "proponer_contacto",
                {"nombre": "Sofía López", "alias": "Sofi", "cuenta_destino": "5566778899", "relacion": "amiga"},
            ),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", "agrega a mi amiga Sofía")

    mcp_client.call.assert_not_called()
    assert len(proposals.PROPOSALS) == 1
    proposal = next(iter(proposals.PROPOSALS.values()))
    assert proposal.tipo == "contacto"
    assert proposal.payload["nombre"] == "Sofía López"


@pytest.mark.asyncio
async def test_handle_message_proponer_contacto_sin_nombre_no_crea_propuesta():
    mcp_client = MagicMock()
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response(
                "proponer_contacto", {"alias": "Sofi", "cuenta_destino": "5566778899", "relacion": "amiga"}
            ),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", "agrega un contacto")
    assert len(proposals.PROPOSALS) == 0


@pytest.mark.asyncio
async def test_confirm_action_contacto_llama_crear_contacto_en_mcp():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(return_value={"id": 1, "nombre": "Sofía López"})
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    proposal = proposals.crear_propuesta(
        "ana",
        "contacto",
        {"nombre": "Sofía López", "alias": "Sofi", "cuenta_destino": "5566778899", "relacion": "amiga"},
        "Agregar a Sofía López (Sofi) como contacto",
    )
    messages = await orchestrator.confirm_action("ana", proposal.id)
    mcp_client.call.assert_awaited_once_with(
        "crear_contacto",
        {
            "account_id": "ana",
            "nombre": "Sofía López",
            "alias": "Sofi",
            "cuenta_destino": "5566778899",
            "relacion": "amiga",
        },
    )
    assert "createSurface" in messages[0]
    assert proposal.id not in proposals.PROPOSALS


@pytest.mark.asyncio
async def test_handle_message_proponer_gasto_fijo_crea_propuesta_sin_tocar_mcp():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock()
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response(
                "proponer_gasto_fijo",
                {"concepto": "Internet", "monto": 600.0, "frecuencia": "mensual", "proxima_fecha": "2026-10-05"},
            ),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", "tengo un gasto fijo de internet de 600 mensual")
    mcp_client.call.assert_not_called()
    proposal = next(iter(proposals.PROPOSALS.values()))
    assert proposal.tipo == "gasto_fijo"


@pytest.mark.asyncio
async def test_handle_message_proponer_gasto_fijo_monto_no_positivo_no_crea_propuesta():
    mcp_client = MagicMock()
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response(
                "proponer_gasto_fijo",
                {"concepto": "x", "monto": 0, "frecuencia": "mensual", "proxima_fecha": "2026-10-05"},
            ),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", "gasto de 0")
    assert len(proposals.PROPOSALS) == 0


@pytest.mark.asyncio
async def test_confirm_action_gasto_fijo_llama_crear_gasto_fijo_en_mcp():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(return_value={"id": 1, "concepto": "Internet"})
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    proposal = proposals.crear_propuesta(
        "ana",
        "gasto_fijo",
        {"concepto": "Internet", "monto": 600.0, "frecuencia": "mensual", "proxima_fecha": "2026-10-05"},
        "Agregar gasto fijo: Internet ($600.00 mensual)",
    )
    messages = await orchestrator.confirm_action("ana", proposal.id)
    mcp_client.call.assert_awaited_once_with(
        "crear_gasto_fijo",
        {
            "account_id": "ana",
            "concepto": "Internet",
            "monto": 600.0,
            "frecuencia": "mensual",
            "proxima_fecha": "2026-10-05",
        },
    )
    assert "createSurface" in messages[0]


@pytest.mark.asyncio
async def test_handle_message_proponer_ingreso_programado_crea_propuesta_sin_tocar_mcp():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock()
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response(
                "proponer_ingreso_programado",
                {"descripcion": "Bono", "monto": 5000.0, "frecuencia": "anual", "proxima_fecha": "2026-12-01"},
            ),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", "voy a recibir un bono anual de 5000")
    mcp_client.call.assert_not_called()
    proposal = next(iter(proposals.PROPOSALS.values()))
    assert proposal.tipo == "ingreso_programado"


@pytest.mark.asyncio
async def test_handle_message_proponer_ingreso_programado_monto_no_positivo_no_crea_propuesta():
    mcp_client = MagicMock()
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response(
                "proponer_ingreso_programado",
                {"descripcion": "x", "monto": 0, "frecuencia": "anual", "proxima_fecha": "2026-12-01"},
            ),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", "ingreso de 0")
    assert len(proposals.PROPOSALS) == 0


@pytest.mark.asyncio
async def test_confirm_action_ingreso_programado_llama_crear_ingreso_programado_en_mcp():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(return_value={"id": 1, "descripcion": "Bono"})
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    proposal = proposals.crear_propuesta(
        "ana",
        "ingreso_programado",
        {"descripcion": "Bono", "monto": 5000.0, "frecuencia": "anual", "proxima_fecha": "2026-12-01"},
        "Agregar ingreso programado: Bono ($5000.00 anual)",
    )
    messages = await orchestrator.confirm_action("ana", proposal.id)
    mcp_client.call.assert_awaited_once_with(
        "crear_ingreso_programado",
        {
            "account_id": "ana",
            "descripcion": "Bono",
            "monto": 5000.0,
            "frecuencia": "anual",
            "proxima_fecha": "2026-12-01",
        },
    )
    assert "createSurface" in messages[0]


@pytest.mark.asyncio
async def test_handle_message_proponer_meta_crea_propuesta_sin_tocar_mcp():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock()
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response(
                "proponer_meta",
                {"descripcion": "Viaje", "monto_objetivo": 20000.0, "fecha_objetivo": "2027-01-01"},
            ),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", "quiero ahorrar para un viaje")
    mcp_client.call.assert_not_called()
    proposal = next(iter(proposals.PROPOSALS.values()))
    assert proposal.tipo == "meta"


@pytest.mark.asyncio
async def test_handle_message_proponer_meta_monto_no_positivo_no_crea_propuesta():
    mcp_client = MagicMock()
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response(
                "proponer_meta", {"descripcion": "x", "monto_objetivo": 0, "fecha_objetivo": "2027-01-01"}
            ),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", "meta de 0")
    assert len(proposals.PROPOSALS) == 0


@pytest.mark.asyncio
async def test_confirm_action_meta_llama_crear_meta_en_mcp():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(return_value={"id": 1, "descripcion": "Viaje"})
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    proposal = proposals.crear_propuesta(
        "ana",
        "meta",
        {"descripcion": "Viaje", "monto_objetivo": 20000.0, "fecha_objetivo": "2027-01-01"},
        "Crear meta: Viaje ($20000.00)",
    )
    messages = await orchestrator.confirm_action("ana", proposal.id)
    mcp_client.call.assert_awaited_once_with(
        "crear_meta",
        {"account_id": "ana", "descripcion": "Viaje", "monto_objetivo": 20000.0, "fecha_objetivo": "2027-01-01"},
    )
    assert "createSurface" in messages[0]
```

- [ ] **Step 2: Correr y verificar que fallan**

Nota: no usar `-k "contacto or gasto_fijo or ingreso_programado or meta"` — ya existen tests de transferencia con "contacto" en el nombre (ej. `test_handle_message_buscar_contacto_reenvia_query`, `test_confirm_action_transferencia_revalida_contacto_y_ejecuta`) que matchearían de más y siguen pasando, ensuciando el resultado. Seleccionar los 12 tests nuevos explícitamente:

Run: `uv run pytest tests/backend/test_orchestrator.py::test_handle_message_proponer_contacto_crea_propuesta_sin_tocar_mcp tests/backend/test_orchestrator.py::test_handle_message_proponer_contacto_sin_nombre_no_crea_propuesta tests/backend/test_orchestrator.py::test_confirm_action_contacto_llama_crear_contacto_en_mcp tests/backend/test_orchestrator.py::test_handle_message_proponer_gasto_fijo_crea_propuesta_sin_tocar_mcp tests/backend/test_orchestrator.py::test_handle_message_proponer_gasto_fijo_monto_no_positivo_no_crea_propuesta tests/backend/test_orchestrator.py::test_confirm_action_gasto_fijo_llama_crear_gasto_fijo_en_mcp tests/backend/test_orchestrator.py::test_handle_message_proponer_ingreso_programado_crea_propuesta_sin_tocar_mcp tests/backend/test_orchestrator.py::test_handle_message_proponer_ingreso_programado_monto_no_positivo_no_crea_propuesta tests/backend/test_orchestrator.py::test_confirm_action_ingreso_programado_llama_crear_ingreso_programado_en_mcp tests/backend/test_orchestrator.py::test_handle_message_proponer_meta_crea_propuesta_sin_tocar_mcp tests/backend/test_orchestrator.py::test_handle_message_proponer_meta_monto_no_positivo_no_crea_propuesta tests/backend/test_orchestrator.py::test_confirm_action_meta_llama_crear_meta_en_mcp -v`
Expected: FAIL en los 12 tests — `AssertionError` o `Function calls do not have a name matching a known tool` (el modelo mockeado devuelve una tool que el orquestador aún no reconoce).

- [ ] **Step 3: Implementar en `src/me_alcanza/backend/orchestrator.py`**

3a. Agregar las 4 `FunctionDeclaration` nuevas dentro de la lista `function_declarations=[...]` en `read_only_tool_declarations()`, justo después del bloque de `proponer_apartado` (después de la línea 236, antes del `]` que cierra la lista):

```python
                types.FunctionDeclaration(
                    name="proponer_contacto",
                    description=(
                        "Propone agregar un contacto/beneficiario nuevo a la lista del usuario. "
                        "NO lo crea: solo genera una propuesta que el usuario debe confirmar "
                        "explícitamente en la UI."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "nombre": types.Schema(type=types.Type.STRING),
                            "alias": types.Schema(type=types.Type.STRING),
                            "cuenta_destino": types.Schema(type=types.Type.STRING),
                            "relacion": types.Schema(type=types.Type.STRING),
                        },
                        required=["nombre", "alias", "cuenta_destino", "relacion"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="proponer_gasto_fijo",
                    description=(
                        "Propone agregar un gasto fijo recurrente nuevo (ej. renta, colegiatura) a "
                        "la cuenta del usuario. NO lo crea: solo genera una propuesta que el usuario "
                        "debe confirmar explícitamente en la UI."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "concepto": types.Schema(type=types.Type.STRING),
                            "monto": types.Schema(type=types.Type.NUMBER),
                            "frecuencia": types.Schema(type=types.Type.STRING),
                            "proxima_fecha": types.Schema(
                                type=types.Type.STRING, description="Formato YYYY-MM-DD."
                            ),
                        },
                        required=["concepto", "monto", "frecuencia", "proxima_fecha"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="proponer_ingreso_programado",
                    description=(
                        "Propone agregar un ingreso recurrente nuevo (ej. nómina, renta cobrada) a "
                        "la cuenta del usuario. NO lo crea: solo genera una propuesta que el usuario "
                        "debe confirmar explícitamente en la UI."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "descripcion": types.Schema(type=types.Type.STRING),
                            "monto": types.Schema(type=types.Type.NUMBER),
                            "frecuencia": types.Schema(type=types.Type.STRING),
                            "proxima_fecha": types.Schema(
                                type=types.Type.STRING, description="Formato YYYY-MM-DD."
                            ),
                        },
                        required=["descripcion", "monto", "frecuencia", "proxima_fecha"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="proponer_meta",
                    description=(
                        "Propone crear una meta de ahorro nueva. NO la crea: solo genera una "
                        "propuesta que el usuario debe confirmar explícitamente en la UI."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "descripcion": types.Schema(type=types.Type.STRING),
                            "monto_objetivo": types.Schema(type=types.Type.NUMBER),
                            "fecha_objetivo": types.Schema(
                                type=types.Type.STRING, description="Formato YYYY-MM-DD."
                            ),
                        },
                        required=["descripcion", "monto_objetivo", "fecha_objetivo"],
                    ),
                ),
```

3b. En `_dispatch_tool_call`, agregar 4 ramas nuevas justo antes del `return {"error": f"Herramienta no permitida: {call.name}"}` final:

```python
        if call.name == "proponer_contacto":
            return self._proponer_contacto(account_id, call.args)

        if call.name == "proponer_gasto_fijo":
            return self._proponer_gasto_fijo(account_id, call.args)

        if call.name == "proponer_ingreso_programado":
            return self._proponer_ingreso_programado(account_id, call.args)

        if call.name == "proponer_meta":
            return self._proponer_meta(account_id, call.args)

        return {"error": f"Herramienta no permitida: {call.name}"}
```

3c. Agregar los 4 métodos nuevos en la clase `Orchestrator`, justo después de `_proponer_apartado`:

```python
    def _proponer_contacto(self, account_id: str, args: dict) -> dict:
        args = args or {}
        nombre = args.get("nombre")
        alias = args.get("alias")
        cuenta_destino = args.get("cuenta_destino")
        relacion = args.get("relacion")
        if not nombre:
            return {"error": "Falta el argumento requerido: nombre"}
        if not alias:
            return {"error": "Falta el argumento requerido: alias"}
        if not cuenta_destino:
            return {"error": "Falta el argumento requerido: cuenta_destino"}
        if not relacion:
            return {"error": "Falta el argumento requerido: relacion"}

        proposal = proposals.crear_propuesta(
            account_id=account_id,
            tipo="contacto",
            payload={
                "nombre": nombre,
                "alias": alias,
                "cuenta_destino": cuenta_destino,
                "relacion": relacion,
            },
            resumen=f"Agregar a {nombre} ({alias}) como contacto",
        )
        return {"proposalId": proposal.id, "resumen": proposal.resumen}

    def _proponer_gasto_fijo(self, account_id: str, args: dict) -> dict:
        args = args or {}
        concepto = args.get("concepto")
        monto = args.get("monto")
        frecuencia = args.get("frecuencia")
        proxima_fecha = args.get("proxima_fecha")
        if not concepto:
            return {"error": "Falta el argumento requerido: concepto"}
        if monto is None:
            return {"error": "Falta el argumento requerido: monto"}
        if not frecuencia:
            return {"error": "Falta el argumento requerido: frecuencia"}
        if not proxima_fecha:
            return {"error": "Falta el argumento requerido: proxima_fecha"}

        monto = float(monto)
        if monto <= 0:
            return {"error": "El monto debe ser mayor a cero"}

        proposal = proposals.crear_propuesta(
            account_id=account_id,
            tipo="gasto_fijo",
            payload={
                "concepto": concepto,
                "monto": monto,
                "frecuencia": frecuencia,
                "proxima_fecha": proxima_fecha,
            },
            resumen=f"Agregar gasto fijo: {concepto} (${monto:.2f} {frecuencia})",
        )
        return {"proposalId": proposal.id, "resumen": proposal.resumen}

    def _proponer_ingreso_programado(self, account_id: str, args: dict) -> dict:
        args = args or {}
        descripcion = args.get("descripcion")
        monto = args.get("monto")
        frecuencia = args.get("frecuencia")
        proxima_fecha = args.get("proxima_fecha")
        if not descripcion:
            return {"error": "Falta el argumento requerido: descripcion"}
        if monto is None:
            return {"error": "Falta el argumento requerido: monto"}
        if not frecuencia:
            return {"error": "Falta el argumento requerido: frecuencia"}
        if not proxima_fecha:
            return {"error": "Falta el argumento requerido: proxima_fecha"}

        monto = float(monto)
        if monto <= 0:
            return {"error": "El monto debe ser mayor a cero"}

        proposal = proposals.crear_propuesta(
            account_id=account_id,
            tipo="ingreso_programado",
            payload={
                "descripcion": descripcion,
                "monto": monto,
                "frecuencia": frecuencia,
                "proxima_fecha": proxima_fecha,
            },
            resumen=f"Agregar ingreso programado: {descripcion} (${monto:.2f} {frecuencia})",
        )
        return {"proposalId": proposal.id, "resumen": proposal.resumen}

    def _proponer_meta(self, account_id: str, args: dict) -> dict:
        args = args or {}
        descripcion = args.get("descripcion")
        monto_objetivo = args.get("monto_objetivo")
        fecha_objetivo = args.get("fecha_objetivo")
        if not descripcion:
            return {"error": "Falta el argumento requerido: descripcion"}
        if monto_objetivo is None:
            return {"error": "Falta el argumento requerido: monto_objetivo"}
        if not fecha_objetivo:
            return {"error": "Falta el argumento requerido: fecha_objetivo"}

        monto_objetivo = float(monto_objetivo)
        if monto_objetivo <= 0:
            return {"error": "El monto_objetivo debe ser mayor a cero"}

        proposal = proposals.crear_propuesta(
            account_id=account_id,
            tipo="meta",
            payload={
                "descripcion": descripcion,
                "monto_objetivo": monto_objetivo,
                "fecha_objetivo": fecha_objetivo,
            },
            resumen=f"Crear meta: {descripcion} (${monto_objetivo:.2f})",
        )
        return {"proposalId": proposal.id, "resumen": proposal.resumen}
```

3d. En `confirm_action`, agregar 4 ramas nuevas dentro del bloque `try:`, justo antes de `return error_a2ui_block(f"Tipo de propuesta desconocido: {proposal.tipo}")`:

```python
            if proposal.tipo == "contacto":
                await self._mcp.call(
                    "crear_contacto",
                    {
                        "account_id": account_id,
                        "nombre": proposal.payload["nombre"],
                        "alias": proposal.payload["alias"],
                        "cuenta_destino": proposal.payload["cuenta_destino"],
                        "relacion": proposal.payload["relacion"],
                    },
                )
                return _confirmation_a2ui_block(
                    f"Contacto {proposal.payload['nombre']} agregado correctamente."
                )

            if proposal.tipo == "gasto_fijo":
                await self._mcp.call(
                    "crear_gasto_fijo",
                    {
                        "account_id": account_id,
                        "concepto": proposal.payload["concepto"],
                        "monto": proposal.payload["monto"],
                        "frecuencia": proposal.payload["frecuencia"],
                        "proxima_fecha": proposal.payload["proxima_fecha"],
                    },
                )
                return _confirmation_a2ui_block(
                    f"Gasto fijo '{proposal.payload['concepto']}' agregado correctamente."
                )

            if proposal.tipo == "ingreso_programado":
                await self._mcp.call(
                    "crear_ingreso_programado",
                    {
                        "account_id": account_id,
                        "descripcion": proposal.payload["descripcion"],
                        "monto": proposal.payload["monto"],
                        "frecuencia": proposal.payload["frecuencia"],
                        "proxima_fecha": proposal.payload["proxima_fecha"],
                    },
                )
                return _confirmation_a2ui_block(
                    f"Ingreso programado '{proposal.payload['descripcion']}' agregado correctamente."
                )

            if proposal.tipo == "meta":
                await self._mcp.call(
                    "crear_meta",
                    {
                        "account_id": account_id,
                        "descripcion": proposal.payload["descripcion"],
                        "monto_objetivo": proposal.payload["monto_objetivo"],
                        "fecha_objetivo": proposal.payload["fecha_objetivo"],
                    },
                )
                return _confirmation_a2ui_block(
                    f"Meta '{proposal.payload['descripcion']}' creada correctamente."
                )

            return error_a2ui_block(f"Tipo de propuesta desconocido: {proposal.tipo}")
```

3e. En `build_system_prompt()`, agregar al final del string de `workflow_description` (dentro del mismo paréntesis, como una cadena más en la concatenación implícita — justo antes del `)` que cierra `workflow_description=(...)`):

```python
            "Para agregar datos nuevos que el usuario mencione en la conversación (un "
            "contacto/beneficiario nuevo, un gasto fijo nuevo, un ingreso programado nuevo, o una "
            "meta de ahorro nueva), usa 'proponer_contacto', 'proponer_gasto_fijo', "
            "'proponer_ingreso_programado' o 'proponer_meta' según corresponda, y muestra una "
            "tarjeta de confirmación con el mismo patrón de 'confirmar_accion' + proposalId que ya "
            "usas para transferencias y apartados. Nunca afirmes que un contacto, gasto fijo, "
            "ingreso programado o meta ya se guardó: solo se crean cuando el usuario confirma "
            "explícitamente. Estas herramientas son solo para CREAR: editar o borrar un contacto/"
            "gasto fijo/ingreso programado/meta existente no se hace por chat, dile al usuario que "
            "lo haga desde la pantalla correspondiente."
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/backend/test_orchestrator.py -v`
Expected: PASS — todos, incluyendo los 12 nuevos.

- [ ] **Step 5: Correr toda la suite completa**

Run: `uv run pytest tests/ -v`
Expected: PASS — todos los tests del proyecto (backend + mcp_bank).

- [ ] **Step 6: Commit**

```bash
git add src/me_alcanza/backend/orchestrator.py tests/backend/test_orchestrator.py
git commit -m "feat: add proponer_X flow for contacto/gasto_fijo/ingreso_programado/meta"
```
