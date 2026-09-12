# Explicabilidad + Score de salud financiera — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (A) cada tarjeta con un número calculado trae un botón "¿Cómo se calculó?" que abre un `Modal` con el desglose — 100% prompt engineering, cero frontend nuevo. (B) un score 0-100 de salud financiera, determinista, reusando la detección de sugerencias proactivas.

**Architecture:** Parte A es un cambio de constantes/prompt en `orchestrator.py`. Parte B agrega una función pura de scoring a `sugerencias_engine.py`, una tool MCP, un DTO y una ruta REST — mismo patrón que el resto del proyecto.

**Tech Stack:** Mismo stack existente. Sin dependencias nuevas.

**Spec:** `docs/superpowers/specs/2026-09-12-explicabilidad-score-design.md`

**Depende de:** `docs/superpowers/plans/2026-09-12-sugerencias-proactivas.md` ya mergeado — Task 2 de este plan importa `sugerencias_engine.detectar_riesgo_liquidez`/`detectar_gastos_fijos_proximos`/`detectar_metas_en_riesgo`, que ese plan ya crea. No empezar este plan si ese no está mergeado.

## Global Constraints

- El score y la explicabilidad son deterministas — el LLM nunca calcula el score ni decide los factores; solo narra lo que el `Modal` explica.
- El score nunca se expone como tool al LLM (no se agrega a `_READ_ONLY_TOOLS`).
- Pesos del score son constantes en el módulo (no hardcodear números mágicos repetidos).
- TDD en todo. Sin cambios a `frontend/`/`flutter_app/`. Sin atribución IA en commits.

---

### Task 1: Explicabilidad — habilitar `Modal` + instrucción en el prompt

**Files:**
- Modify: `src/me_alcanza/backend/orchestrator.py`
- Test: `tests/backend/test_orchestrator.py`

**Interfaces:**
- Consumes: nada nuevo.
- Produces: `_ALLOWED_COMPONENTS` con `"Modal"`, `ui_description` actualizado.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/backend/test_orchestrator.py`:

```python
def test_modal_esta_en_allowed_components():
    from me_alcanza.backend.orchestrator import _ALLOWED_COMPONENTS

    assert "Modal" in _ALLOWED_COMPONENTS


def test_system_prompt_instruye_explicabilidad():
    prompt = build_system_prompt()
    assert "Modal" in prompt
    assert "Cómo se calculó" in prompt
```

(`build_system_prompt` ya está importado en el archivo — si no lo está, agrégalo al import existente de `me_alcanza.backend.orchestrator`.)

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/backend/test_orchestrator.py::test_modal_esta_en_allowed_components tests/backend/test_orchestrator.py::test_system_prompt_instruye_explicabilidad -v`
Expected: FAIL — `"Modal"` no está en la lista, el texto no está en el prompt.

- [ ] **Step 3: Implementar en `src/me_alcanza/backend/orchestrator.py`**

3a. Cambiar la línea de `_ALLOWED_COMPONENTS`:

```python
_ALLOWED_COMPONENTS = ["Card", "Column", "Row", "Text", "Button", "List", "Divider", "Modal"]
```

3b. En `build_system_prompt()`, dentro de `ui_description=(...)`, agregar al final (antes del `)` que cierra la cadena), como un punto 6:

```python
            "6) Para cualquier tarjeta que muestre un número calculado o derivado (un saldo "
            "proyectado, el margen de 'simular_flujo_de_caja', el desglose de una transferencia con "
            "puntos, etc.), agrega un Button variant='borderless' con texto '¿Cómo se calculó?' cuyo "
            "'trigger' abra un Modal cuyo 'content' sea una Column mostrando los montos y fechas "
            "concretos que entraron a ese cálculo. Nunca agregues este botón para datos que ya son "
            "un valor directo de una herramienta (ej. el saldo actual tal cual, sin proyección) — "
            "solo para números que el LLM o una herramienta derivaron a partir de otros datos."
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/backend/test_orchestrator.py -v`
Expected: PASS — todos, incluyendo los 2 nuevos.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/backend/orchestrator.py tests/backend/test_orchestrator.py
git commit -m "feat: enable Modal component and prompt guidance for explainability"
```

---

### Task 2: `sugerencias_engine.py` — función de score de salud financiera

**Files:**
- Modify: `src/me_alcanza/mcp_bank/sugerencias_engine.py`
- Test: `tests/mcp_bank/test_sugerencias_engine.py`

**Interfaces:**
- Consumes: `detectar_riesgo_liquidez`/`detectar_gastos_fijos_proximos`/`detectar_metas_en_riesgo` (ya existentes en este mismo archivo, del plan de sugerencias proactivas).
- Produces: `calcular_score_salud_financiera(saldo_actual, ingresos, gastos, metas, apartados_activos, hoy) -> dict` — consumido por Task 3.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/mcp_bank/test_sugerencias_engine.py`:

```python
def test_score_perfecto_sin_riesgos_ni_apartados():
    resultado = engine.calcular_score_salud_financiera(
        saldo_actual=10000.0, ingresos=[], gastos=[], metas=[], apartados_activos=0, hoy=date.today().isoformat()
    )
    assert resultado["score"] == 100
    assert resultado["categoria"] == "Saludable"


def test_score_baja_con_riesgo_de_liquidez():
    # Nota: el mismo gasto (5000, en +2 días, >= 30% del saldo de 200) dispara
    # AMBAS reglas: riesgo_liquidez (-30) y gasto_fijo_proximo (-5, 1 gasto).
    # Score esperado: 100 - 30 - 5 = 65.
    hoy = date.today()
    ingresos = [{"monto": 100.0, "proxima_fecha": (hoy + timedelta(days=10)).isoformat()}]
    gastos = [{"monto": 5000.0, "proxima_fecha": (hoy + timedelta(days=2)).isoformat()}]
    resultado = engine.calcular_score_salud_financiera(
        saldo_actual=200.0, ingresos=ingresos, gastos=gastos, metas=[], apartados_activos=0, hoy=hoy.isoformat()
    )
    assert resultado["score"] == 65
    assert any("saldo" in f.lower() for f in resultado["factores"])


def test_score_sube_con_apartado_activo():
    resultado = engine.calcular_score_salud_financiera(
        saldo_actual=10000.0, ingresos=[], gastos=[], metas=[], apartados_activos=1, hoy=date.today().isoformat()
    )
    assert resultado["score"] == 100  # ya estaba en el tope, el clamp no deja subir de 100
    assert any("ahorro" in f.lower() for f in resultado["factores"])


def test_score_categoria_riesgo_cuando_muy_bajo():
    # riesgo_liquidez (-30) + gasto_fijo_proximo (-5, 1 gasto) + 3 metas en
    # riesgo (min(3*10, 20) = -20). Score esperado: 100 - 30 - 5 - 20 = 45.
    hoy = date.today()
    ingresos = [{"monto": 100.0, "proxima_fecha": (hoy + timedelta(days=10)).isoformat()}]
    gastos = [{"monto": 5000.0, "proxima_fecha": (hoy + timedelta(days=2)).isoformat()}]
    metas = [
        {"id": i, "descripcion": f"Meta {i}", "monto_objetivo": 100.0, "monto_ahorrado": 0.0,
         "fecha_objetivo": (hoy + timedelta(days=5)).isoformat()}
        for i in range(3)
    ]
    resultado = engine.calcular_score_salud_financiera(
        saldo_actual=200.0, ingresos=ingresos, gastos=gastos, metas=metas, apartados_activos=0, hoy=hoy.isoformat()
    )
    assert resultado["score"] == 45
    assert resultado["categoria"] == "Riesgo"
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_sugerencias_engine.py -k score -v`
Expected: FAIL — `AttributeError`.

- [ ] **Step 3: Implementar en `src/me_alcanza/mcp_bank/sugerencias_engine.py`**

Agregar al final del archivo:

```python
PENALIZACION_RIESGO_LIQUIDEZ = 30
PENALIZACION_POR_GASTO_PROXIMO = 5
PENALIZACION_MAX_GASTOS = 20
PENALIZACION_POR_META_EN_RIESGO = 10
PENALIZACION_MAX_METAS = 20
BONO_APARTADO_ACTIVO = 10


def calcular_score_salud_financiera(
    saldo_actual: float,
    ingresos: list[dict],
    gastos: list[dict],
    metas: list[dict],
    apartados_activos: int,
    hoy: str,
) -> dict:
    riesgo_liquidez = detectar_riesgo_liquidez(saldo_actual, ingresos, gastos, hoy)
    gastos_proximos = detectar_gastos_fijos_proximos(gastos, saldo_actual, hoy)
    metas_en_riesgo = detectar_metas_en_riesgo(metas, hoy)

    score = 100
    factores = []

    if riesgo_liquidez:
        score -= PENALIZACION_RIESGO_LIQUIDEZ
        factores.append("Tu saldo se proyecta insuficiente antes de tu próximo ingreso programado.")

    penalizacion_gastos = min(len(gastos_proximos) * PENALIZACION_POR_GASTO_PROXIMO, PENALIZACION_MAX_GASTOS)
    if penalizacion_gastos:
        factores.append(
            f"{len(gastos_proximos)} gasto(s) fijo(s) próximo(s) representan una parte alta de tu saldo actual."
        )
        score -= penalizacion_gastos

    penalizacion_metas = min(len(metas_en_riesgo) * PENALIZACION_POR_META_EN_RIESGO, PENALIZACION_MAX_METAS)
    if penalizacion_metas:
        factores.append(f"{len(metas_en_riesgo)} meta(s) de ahorro en riesgo de no cumplirse a tiempo.")
        score -= penalizacion_metas

    if apartados_activos > 0:
        score += BONO_APARTADO_ACTIVO
        factores.append("Tienes al menos un apartado de ahorro activo — buen hábito.")

    score = max(0, min(100, score))

    if score >= 80:
        categoria = "Saludable"
    elif score >= 50:
        categoria = "Atención"
    else:
        categoria = "Riesgo"

    if not factores:
        factores.append("No se detectaron riesgos ni hábitos destacados en este momento.")

    return {"score": score, "categoria": categoria, "factores": factores}
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_sugerencias_engine.py -v`
Expected: PASS — todos.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/mcp_bank/sugerencias_engine.py tests/mcp_bank/test_sugerencias_engine.py
git commit -m "feat: add deterministic financial health score calculation"
```

---

### Task 3: `server.py` — exponer `calcular_score_salud_financiera`

**Files:**
- Modify: `src/me_alcanza/mcp_bank/server.py`
- Test: `tests/mcp_bank/test_server.py`

**Interfaces:**
- Consumes: `sugerencias_engine.calcular_score_salud_financiera` (Task 2); `db.get_saldo`/`get_ingresos_programados`/`get_gastos_fijos`/`get_metas`/`listar_apartados` (ya existentes).
- Produces: tool MCP `calcular_score_salud_financiera(account_id) -> dict` — consumida por Task 5.

- [ ] **Step 1: Actualizar el test del set exacto de tools + agregar test de integración**

En `tests/mcp_bank/test_server.py`, agregar `"calcular_score_salud_financiera"` al set esperado de `test_mcp_server_expone_las_tools_esperadas`.

Agregar al final del archivo:

```python
@pytest.mark.asyncio
async def test_mcp_server_calcular_score_salud_financiera(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with stdio_client(_params(db_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            resultado = await _call(session, "calcular_score_salud_financiera", {"account_id": "ana"})
            assert 0 <= resultado["score"] <= 100
            assert resultado["categoria"] in {"Saludable", "Atención", "Riesgo"}
            assert isinstance(resultado["factores"], list)
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_server.py -v`
Expected: FAIL — tool-set incompleto, tool nueva no existe.

- [ ] **Step 3: Implementar en `src/me_alcanza/mcp_bank/server.py`**

Agregar al final del archivo (antes de `if __name__ == "__main__":`):

```python
@mcp.tool()
def calcular_score_salud_financiera(account_id: str) -> dict:
    """Calcula un score 0-100 de salud financiera de la cuenta, con los factores que lo explican."""
    conn = _connection()
    try:
        saldo = db.get_saldo(conn, account_id)
        if saldo is None:
            raise ValueError(f"Cuenta no encontrada: {account_id}")
        ingresos = db.get_ingresos_programados(conn, account_id)
        gastos = db.get_gastos_fijos(conn, account_id)
        metas = db.get_metas(conn, account_id)
        apartados = db.listar_apartados(conn, account_id)
        apartados_activos = sum(1 for a in apartados if a["estado"] == "activo")

        return sugerencias_engine.calcular_score_salud_financiera(
            saldo_actual=saldo["saldo"],
            ingresos=ingresos,
            gastos=gastos,
            metas=metas,
            apartados_activos=apartados_activos,
            hoy=date.today().isoformat(),
        )
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    finally:
        conn.close()
```

(El import `from . import cashflow, db, sugerencias_engine` y `from datetime import date` a nivel de módulo ya deberían existir si el plan de sugerencias proactivas ya se ejecutó — si por algún motivo no están, agrégalos.)

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_server.py -v`
Expected: PASS — todos.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/mcp_bank/server.py tests/mcp_bank/test_server.py
git commit -m "feat: expose calcular_score_salud_financiera via MCP server"
```

---

### Task 4: DTO del score

**Files:**
- Modify: `src/me_alcanza/backend/dtos.py`

**Interfaces:**
- Produces: `ScoreSaludResponse` — consumido por Task 5.

- [ ] **Step 1: Implementar en `src/me_alcanza/backend/dtos.py`**

Agregar al final del archivo:

```python
class ScoreSaludResponse(BaseModel):
    score: int
    categoria: str
    factores: list[str]
```

- [ ] **Step 2: Verificar que importa sin errores**

Run: `uv run python3 -c "from me_alcanza.backend import dtos"`
Expected: sin salida, sin excepción.

- [ ] **Step 3: Commit**

```bash
git add src/me_alcanza/backend/dtos.py
git commit -m "feat: add ScoreSaludResponse DTO"
```

---

### Task 5: Ruta REST — score de salud financiera

**Files:**
- Modify: `src/me_alcanza/backend/routes.py`
- Test: `tests/backend/test_routes.py`

**Interfaces:**
- Consumes: `ScoreSaludResponse` (Task 4); tool MCP `calcular_score_salud_financiera` (Task 3).
- Produces: `GET /api/score-salud-financiera`.

- [ ] **Step 1: Escribir el test que falla**

Agregar al final de `tests/backend/test_routes.py`:

```python
def test_get_score_salud_financiera(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.get("/api/score-salud-financiera", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        body = response.json()
        assert 0 <= body["score"] <= 100
        assert body["categoria"] in {"Saludable", "Atención", "Riesgo"}
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `uv run pytest tests/backend/test_routes.py::test_get_score_salud_financiera -v`
Expected: FAIL — 404 Not Found.

- [ ] **Step 3: Implementar en `src/me_alcanza/backend/routes.py`**

Actualizar el import de `.dtos` agregando `ScoreSaludResponse`.

Agregar al final del archivo:

```python
@router.get("/score-salud-financiera", response_model=ScoreSaludResponse)
async def get_score_salud_financiera(
    request: Request, account_id: str = Depends(auth.get_current_account_id)
) -> ScoreSaludResponse:
    try:
        resultado = await request.app.state.mcp_client.call(
            "calcular_score_salud_financiera", {"account_id": account_id}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ScoreSaludResponse(**resultado)
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
git commit -m "feat: add GET /api/score-salud-financiera route"
```
