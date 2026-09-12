# Sugerencias proactivas — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detectar 3 situaciones de riesgo financiero con reglas deterministas (sin LLM) y exponerlas vía REST con historial (pendiente/atendida/descartada), para llenar la pestaña Dashboard.

**Architecture:** Funciones puras de detección (`sugerencias_engine.py`, mismo estilo que `cashflow.py`) + CRUD simple en `db.py` (tabla `sugerencias`) + orquestación en `server.py` (fetch de datos + detección + deduplicación + persistencia, mismo patrón que la tool `simular_flujo_de_caja` ya existente) + rutas REST. El LLM nunca ve ni genera esto.

**Tech Stack:** Mismo stack existente. Sin dependencias nuevas (usa `json` de la stdlib para el campo `detalle`).

**Spec:** `docs/superpowers/specs/2026-09-12-sugerencias-proactivas-design.md`

## Global Constraints

- Las 3 reglas son funciones puras en `sugerencias_engine.py`: reciben datos ya consultados (no tocan `conn` ni hacen I/O), devuelven listas de dicts candidatos.
- `entidad_id` siempre es `NOT NULL` — usa el literal `"global"` para `riesgo_liquidez` (no hay una entidad específica), el `id` real (como string) del gasto fijo o meta para los otros dos tipos.
- Deduplicación: nunca insertar una sugerencia nueva si ya existe una con `estado='pendiente'` del mismo `tipo` + `entidad_id` para esa cuenta.
- Ninguna tool de este plan se agrega a `_READ_ONLY_TOOLS` ni a `read_only_tool_declarations()` — el LLM no tiene acceso, ni de lectura ni de escritura, a las sugerencias.
- Umbrales de las reglas (constantes en `sugerencias_engine.py`): gasto próximo ≤ 5 días y ≥ 30% del saldo; meta en riesgo ≤ 30 días sin completar.
- TDD en todo. Sin cambios a `frontend/`/`flutter_app/`. Sin atribución IA en commits.

---

### Task 1: `sugerencias_engine.py` — las 3 reglas de detección (funciones puras)

**Files:**
- Create: `src/me_alcanza/mcp_bank/sugerencias_engine.py`
- Test: `tests/mcp_bank/test_sugerencias_engine.py`

**Interfaces:**
- Consumes: nada (funciones puras sobre datos ya en memoria).
- Produces: `detectar_riesgo_liquidez(saldo_actual, ingresos, gastos, hoy) -> list[dict]`, `detectar_gastos_fijos_proximos(gastos_fijos, saldo_actual, hoy) -> list[dict]`, `detectar_metas_en_riesgo(metas, hoy) -> list[dict]` — cada dict candidato tiene forma `{"tipo": str, "entidad_id": str, "detalle": dict}`. Consumidas por Task 3.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/mcp_bank/test_sugerencias_engine.py`:

```python
from datetime import date, timedelta

from me_alcanza.mcp_bank import sugerencias_engine as engine


def test_detectar_riesgo_liquidez_cuando_no_alcanza():
    hoy = date.today().isoformat()
    proxima_quincena = (date.today() + timedelta(days=10)).isoformat()
    ingresos = [{"monto": 100.0, "proxima_fecha": proxima_quincena}]
    gastos = [{"monto": 5000.0, "proxima_fecha": (date.today() + timedelta(days=2)).isoformat()}]
    candidatos = engine.detectar_riesgo_liquidez(saldo_actual=200.0, ingresos=ingresos, gastos=gastos, hoy=hoy)
    assert len(candidatos) == 1
    assert candidatos[0]["tipo"] == "riesgo_liquidez"
    assert candidatos[0]["entidad_id"] == "global"
    assert candidatos[0]["detalle"]["margen"] < 0


def test_detectar_riesgo_liquidez_cuando_si_alcanza():
    hoy = date.today().isoformat()
    proxima_quincena = (date.today() + timedelta(days=10)).isoformat()
    ingresos = [{"monto": 100000.0, "proxima_fecha": proxima_quincena}]
    gastos = []
    candidatos = engine.detectar_riesgo_liquidez(saldo_actual=5000.0, ingresos=ingresos, gastos=gastos, hoy=hoy)
    assert candidatos == []


def test_detectar_riesgo_liquidez_sin_ingresos_programados():
    hoy = date.today().isoformat()
    candidatos = engine.detectar_riesgo_liquidez(saldo_actual=100.0, ingresos=[], gastos=[], hoy=hoy)
    assert candidatos == []


def test_detectar_gastos_fijos_proximos_dispara_por_fecha_y_monto():
    hoy = date.today()
    gastos_fijos = [
        {"id": 1, "concepto": "Renta", "monto": 4000.0, "proxima_fecha": (hoy + timedelta(days=3)).isoformat()},
        {"id": 2, "concepto": "Internet", "monto": 500.0, "proxima_fecha": (hoy + timedelta(days=3)).isoformat()},
        {"id": 3, "concepto": "Seguro", "monto": 4000.0, "proxima_fecha": (hoy + timedelta(days=20)).isoformat()},
    ]
    candidatos = engine.detectar_gastos_fijos_proximos(gastos_fijos, saldo_actual=10000.0, hoy=hoy.isoformat())
    assert len(candidatos) == 1
    assert candidatos[0]["entidad_id"] == "1"
    assert candidatos[0]["detalle"]["concepto"] == "Renta"


def test_detectar_metas_en_riesgo_dispara_si_falta_poco_y_no_completada():
    hoy = date.today()
    metas = [
        {
            "id": 7,
            "descripcion": "Viaje",
            "monto_objetivo": 10000.0,
            "monto_ahorrado": 1000.0,
            "fecha_objetivo": (hoy + timedelta(days=15)).isoformat(),
        },
        {
            "id": 8,
            "descripcion": "Ya completada",
            "monto_objetivo": 500.0,
            "monto_ahorrado": 500.0,
            "fecha_objetivo": (hoy + timedelta(days=10)).isoformat(),
        },
        {
            "id": 9,
            "descripcion": "Falta mucho tiempo",
            "monto_objetivo": 500.0,
            "monto_ahorrado": 0.0,
            "fecha_objetivo": (hoy + timedelta(days=90)).isoformat(),
        },
    ]
    candidatos = engine.detectar_metas_en_riesgo(metas, hoy=hoy.isoformat())
    assert len(candidatos) == 1
    assert candidatos[0]["entidad_id"] == "7"
    assert candidatos[0]["detalle"]["descripcion"] == "Viaje"
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_sugerencias_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'me_alcanza.mcp_bank.sugerencias_engine'`.

- [ ] **Step 3: Implementar `src/me_alcanza/mcp_bank/sugerencias_engine.py`**

```python
from datetime import date, datetime

from . import cashflow

DIAS_UMBRAL_GASTO_PROXIMO = 5
PCT_UMBRAL_GASTO_PROXIMO = 0.30
DIAS_UMBRAL_META_EN_RIESGO = 30


def _parse_fecha(fecha_str: str) -> date:
    return datetime.strptime(fecha_str, "%Y-%m-%d").date()


def detectar_riesgo_liquidez(
    saldo_actual: float, ingresos: list[dict], gastos: list[dict], hoy: str
) -> list[dict]:
    candidatos = []
    for ingreso in ingresos:
        resultado = cashflow.simular_flujo_de_caja(
            saldo_actual=saldo_actual,
            ingresos=ingresos,
            gastos=gastos,
            hoy=hoy,
            fecha_objetivo=ingreso["proxima_fecha"],
            monto_objetivo=0,
        )
        if not resultado["alcanza"]:
            candidatos.append(
                {
                    "tipo": "riesgo_liquidez",
                    "entidad_id": "global",
                    "detalle": {
                        "margen": resultado["margen"],
                        "fecha_critica": resultado["fecha_critica"],
                        "saldo_minimo_proyectado": resultado["saldo_minimo_proyectado"],
                    },
                }
            )
            break  # una sola alerta de liquidez basta, aunque haya varios ingresos
    return candidatos


def detectar_gastos_fijos_proximos(gastos_fijos: list[dict], saldo_actual: float, hoy: str) -> list[dict]:
    hoy_fecha = _parse_fecha(hoy)
    candidatos = []
    for gasto in gastos_fijos:
        dias_restantes = (_parse_fecha(gasto["proxima_fecha"]) - hoy_fecha).days
        if dias_restantes < 0 or dias_restantes > DIAS_UMBRAL_GASTO_PROXIMO:
            continue
        if saldo_actual <= 0 or gasto["monto"] < PCT_UMBRAL_GASTO_PROXIMO * saldo_actual:
            continue
        candidatos.append(
            {
                "tipo": "gasto_fijo_proximo",
                "entidad_id": str(gasto["id"]),
                "detalle": {
                    "concepto": gasto["concepto"],
                    "monto": gasto["monto"],
                    "proxima_fecha": gasto["proxima_fecha"],
                },
            }
        )
    return candidatos


def detectar_metas_en_riesgo(metas: list[dict], hoy: str) -> list[dict]:
    hoy_fecha = _parse_fecha(hoy)
    candidatos = []
    for meta in metas:
        if meta["monto_ahorrado"] >= meta["monto_objetivo"]:
            continue
        dias_restantes = (_parse_fecha(meta["fecha_objetivo"]) - hoy_fecha).days
        if dias_restantes < 0 or dias_restantes > DIAS_UMBRAL_META_EN_RIESGO:
            continue
        candidatos.append(
            {
                "tipo": "meta_en_riesgo",
                "entidad_id": str(meta["id"]),
                "detalle": {
                    "descripcion": meta["descripcion"],
                    "monto_objetivo": meta["monto_objetivo"],
                    "monto_ahorrado": meta["monto_ahorrado"],
                    "fecha_objetivo": meta["fecha_objetivo"],
                },
            }
        )
    return candidatos
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_sugerencias_engine.py -v`
Expected: PASS — todos.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/mcp_bank/sugerencias_engine.py tests/mcp_bank/test_sugerencias_engine.py
git commit -m "feat: add deterministic detection rules for proactive sugerencias"
```

---

### Task 2: `db.py` — tabla `sugerencias` + CRUD

**Files:**
- Modify: `src/me_alcanza/mcp_bank/db.py`
- Test: `tests/mcp_bank/test_db.py`

**Interfaces:**
- Consumes: nada de Task 1 directamente (Task 1 son funciones puras que Task 3 combina con esto).
- Produces: `crear_sugerencia(conn, account_id, tipo, entidad_id, detalle: dict) -> dict`, `existe_sugerencia_pendiente(conn, account_id, tipo, entidad_id) -> bool`, `listar_sugerencias(conn, account_id, estado: str | None = None) -> list[dict]`, `marcar_sugerencia(conn, account_id, sugerencia_id, nuevo_estado: str) -> dict` — consumidos por Task 3.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al `SCHEMA` de `tests/mcp_bank/test_db.py` no aplica (el schema se agrega en `db.py`, no en el test). Agregar al final de `tests/mcp_bank/test_db.py`:

```python
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
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_db.py -k sugerencia -v`
Expected: FAIL — `AttributeError`.

- [ ] **Step 3: Implementar en `src/me_alcanza/mcp_bank/db.py`**

3a. Agregar `import json` al inicio del archivo (junto a los imports existentes de `hashlib`, `hmac`, `os`, `sqlite3`).

3b. Agregar al `SCHEMA` (dentro del mismo bloque de `CREATE TABLE IF NOT EXISTS`, después de la tabla `contactos`):

```sql
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
```

3c. Agregar al final del archivo:

```python
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
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_db.py -v`
Expected: PASS — todos.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/mcp_bank/db.py tests/mcp_bank/test_db.py
git commit -m "feat: add sugerencias table and CRUD to db layer"
```

---

### Task 3: `server.py` — orquestación (detectar + deduplicar + persistir + listar)

**Files:**
- Modify: `src/me_alcanza/mcp_bank/server.py`
- Test: `tests/mcp_bank/test_server.py`

**Interfaces:**
- Consumes: `sugerencias_engine.detectar_*` (Task 1), `db.crear_sugerencia`/`existe_sugerencia_pendiente`/`listar_sugerencias`/`marcar_sugerencia` (Task 2), `db.get_saldo`/`get_ingresos_programados`/`get_gastos_fijos`/`get_metas` (ya existentes).
- Produces: tools MCP `generar_y_listar_sugerencias(account_id) -> list[dict]`, `marcar_sugerencia(account_id, sugerencia_id, nuevo_estado) -> dict` — consumidas por Task 5 (rutas REST).

- [ ] **Step 1: Actualizar el test del set exacto de tools + agregar tests de integración**

En `tests/mcp_bank/test_server.py`, agregar `"generar_y_listar_sugerencias"` y `"marcar_sugerencia"` al set esperado de `test_mcp_server_expone_las_tools_esperadas` (ahora 29 en total, si ya se hizo el plan de `resumen-movimientos` antes que este — si no, ajusta el número base al que corresponda en ese momento).

Agregar al final del archivo:

```python
@pytest.mark.asyncio
async def test_mcp_server_generar_y_listar_sugerencias_detecta_gasto_proximo(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with stdio_client(_params(db_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            sugerencias = await _call(session, "generar_y_listar_sugerencias", {"account_id": "ana"})
            tipos = {s["tipo"] for s in sugerencias}
            # Los datos sembrados de "ana" tienen gastos fijos a 3-4 días con
            # montos que superan el 30% de su saldo (500.00) -> debe disparar.
            assert "gasto_fijo_proximo" in tipos


@pytest.mark.asyncio
async def test_mcp_server_generar_y_listar_sugerencias_no_duplica(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with stdio_client(_params(db_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            primera = await _call(session, "generar_y_listar_sugerencias", {"account_id": "ana"})
            segunda = await _call(session, "generar_y_listar_sugerencias", {"account_id": "ana"})
            assert len(segunda) == len(primera)


@pytest.mark.asyncio
async def test_mcp_server_marcar_sugerencia(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with stdio_client(_params(db_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            sugerencias = await _call(session, "generar_y_listar_sugerencias", {"account_id": "ana"})
            sugerencia_id = sugerencias[0]["id"]
            actualizada = await _call(
                session, "marcar_sugerencia", {"account_id": "ana", "sugerencia_id": sugerencia_id, "nuevo_estado": "atendida"}
            )
            assert actualizada["estado"] == "atendida"
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_server.py -v`
Expected: FAIL — tool-set incompleto, tools nuevas no existen.

- [ ] **Step 3: Implementar en `src/me_alcanza/mcp_bank/server.py`**

Agregar el import al inicio (junto a `from . import cashflow, db`):

```python
from . import cashflow, db, sugerencias_engine
```

Agregar al final del archivo (antes de `if __name__ == "__main__":`):

```python
@mcp.tool()
def generar_y_listar_sugerencias(account_id: str) -> list[dict]:
    """Corre las reglas de detección de riesgo financiero, persiste las sugerencias nuevas
    (sin duplicar las ya pendientes) y devuelve el listado completo de la cuenta."""
    conn = _connection()
    try:
        saldo = db.get_saldo(conn, account_id)
        if saldo is None:
            raise ValueError(f"Cuenta no encontrada: {account_id}")
        ingresos = db.get_ingresos_programados(conn, account_id)
        gastos = db.get_gastos_fijos(conn, account_id)
        metas = db.get_metas(conn, account_id)
        hoy = date.today().isoformat()

        candidatos = (
            sugerencias_engine.detectar_riesgo_liquidez(saldo["saldo"], ingresos, gastos, hoy)
            + sugerencias_engine.detectar_gastos_fijos_proximos(gastos, saldo["saldo"], hoy)
            + sugerencias_engine.detectar_metas_en_riesgo(metas, hoy)
        )
        for candidato in candidatos:
            if not db.existe_sugerencia_pendiente(conn, account_id, candidato["tipo"], candidato["entidad_id"]):
                db.crear_sugerencia(conn, account_id, candidato["tipo"], candidato["entidad_id"], candidato["detalle"])

        return db.listar_sugerencias(conn, account_id)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    finally:
        conn.close()


@mcp.tool()
def marcar_sugerencia(account_id: str, sugerencia_id: int, nuevo_estado: str) -> dict:
    """Marca una sugerencia como 'atendida' o 'descartada'."""
    conn = _connection()
    try:
        return db.marcar_sugerencia(conn, account_id, sugerencia_id, nuevo_estado)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    finally:
        conn.close()
```

Si `from datetime import date` no está ya importado al inicio del archivo, agrégalo (`simular_flujo_de_caja` ya lo importa localmente dentro de su función — para estas dos tools nuevas impórtalo a nivel de módulo junto a `import os`, es más limpio dado que se usa en una tool de nivel superior).

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_server.py -v`
Expected: PASS — todos.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/mcp_bank/server.py tests/mcp_bank/test_server.py
git commit -m "feat: expose sugerencias generation and marking via MCP server"
```

---

### Task 4: DTOs de sugerencias

**Files:**
- Modify: `src/me_alcanza/backend/dtos.py`

**Interfaces:**
- Produces: `SugerenciaResponse`, `MarcarSugerenciaRequest` — consumidos por Task 5.

- [ ] **Step 1: Implementar en `src/me_alcanza/backend/dtos.py`**

Agregar al final del archivo:

```python
class SugerenciaResponse(BaseModel):
    id: int
    tipo: str
    entidad_id: str
    detalle: dict
    estado: str
    created_at: str
    resuelta_at: str | None
```

- [ ] **Step 2: Verificar que importa sin errores**

Run: `uv run python3 -c "from me_alcanza.backend import dtos"`
Expected: sin salida, sin excepción.

- [ ] **Step 3: Commit**

```bash
git add src/me_alcanza/backend/dtos.py
git commit -m "feat: add SugerenciaResponse DTO"
```

---

### Task 5: Rutas REST — listar, atender, descartar sugerencias

**Files:**
- Modify: `src/me_alcanza/backend/routes.py`
- Test: `tests/backend/test_routes.py`

**Interfaces:**
- Consumes: `SugerenciaResponse` (Task 4); tools MCP `generar_y_listar_sugerencias`/`marcar_sugerencia` (Task 3).
- Produces: `GET /api/sugerencias`, `POST /api/sugerencias/{id}/atender`, `POST /api/sugerencias/{id}/descartar`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/backend/test_routes.py`:

```python
def test_get_sugerencias_genera_y_lista(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.get("/api/sugerencias", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert isinstance(response.json(), list)


def test_get_sugerencias_no_duplica_entre_llamadas(app):
    with TestClient(app) as client:
        token = _login(client)
        primera = client.get("/api/sugerencias", headers={"Authorization": f"Bearer {token}"}).json()
        segunda = client.get("/api/sugerencias", headers={"Authorization": f"Bearer {token}"}).json()
        assert len(segunda) == len(primera)


def test_atender_sugerencia(app):
    with TestClient(app) as client:
        token = _login(client)
        sugerencias = client.get("/api/sugerencias", headers={"Authorization": f"Bearer {token}"}).json()
        sugerencia_id = sugerencias[0]["id"]
        response = client.post(
            f"/api/sugerencias/{sugerencia_id}/atender", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["estado"] == "atendida"


def test_descartar_sugerencia_inexistente_devuelve_400(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.post(
            "/api/sugerencias/999999/descartar", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 400
```

Nota: estos tests asumen que la cuenta demo `ana` dispara al menos una
sugerencia con los datos sembrados actuales (gastos fijos a 3-4 días con
monto > 30% de su saldo de $500). Si el seed cambia en el futuro y deja de
disparar ninguna, `sugerencias[0]` en `test_atender_sugerencia` fallaría con
`IndexError` — ajustar el escenario del test si eso ocurre.

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/backend/test_routes.py -k sugerencia -v`
Expected: FAIL — 404 Not Found.

- [ ] **Step 3: Implementar en `src/me_alcanza/backend/routes.py`**

Actualizar el import de `.dtos` agregando `SugerenciaResponse`.

Agregar al final del archivo:

```python
@router.get("/sugerencias", response_model=list[SugerenciaResponse])
async def list_sugerencias(
    request: Request, account_id: str = Depends(auth.get_current_account_id)
) -> list[SugerenciaResponse]:
    try:
        sugerencias = await request.app.state.mcp_client.call(
            "generar_y_listar_sugerencias", {"account_id": account_id}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [SugerenciaResponse(**s) for s in sugerencias]


@router.post("/sugerencias/{sugerencia_id}/atender", response_model=SugerenciaResponse)
async def atender_sugerencia(
    sugerencia_id: int,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> SugerenciaResponse:
    try:
        actualizada = await request.app.state.mcp_client.call(
            "marcar_sugerencia",
            {"account_id": account_id, "sugerencia_id": sugerencia_id, "nuevo_estado": "atendida"},
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SugerenciaResponse(**actualizada)


@router.post("/sugerencias/{sugerencia_id}/descartar", response_model=SugerenciaResponse)
async def descartar_sugerencia(
    sugerencia_id: int,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> SugerenciaResponse:
    try:
        actualizada = await request.app.state.mcp_client.call(
            "marcar_sugerencia",
            {"account_id": account_id, "sugerencia_id": sugerencia_id, "nuevo_estado": "descartada"},
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SugerenciaResponse(**actualizada)
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/backend/test_routes.py -v`
Expected: PASS — todos.

- [ ] **Step 5: Correr toda la suite**

Run: `uv run pytest tests/ -v`
Expected: PASS — todos los tests del proyecto.

- [ ] **Step 6: Commit**

```bash
git add src/me_alcanza/backend/routes.py tests/backend/test_routes.py
git commit -m "feat: add REST endpoints for sugerencias (list, atender, descartar)"
```
