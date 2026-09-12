# Backend FastAPI (orquestación LLM↔MCP + A2UI) — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el backend FastAPI de `me-alcanza`: autenticación JWT, cliente del MCP "core-bancario" (ya construido y mergeado), un orquestador que hace tool-calling con Gemini y genera bloques A2UI, el contrato genérico de propuesta/confirmación (apartado de ahorro + transferencia con desambiguación de contacto), y las rutas `/api/login`, `/api/chat`, `/api/confirm-action`.

**Architecture:** Extiende el patrón ya probado en `prueba-ui-generativa` (MCP por stdio + FastAPI que orquesta Gemini↔MCP + A2UI `direct_json`), adaptado a los tools nuevos del MCP de `me-alcanza` (flujo de caja, ingresos/gastos programados, metas, contactos) y a un contrato de propuesta genérico (no solo transferencias). Bottom-up: primero una tool nueva que falta en el MCP (`get_contacto` por id, necesaria para resolver transferencias de forma segura), luego auth, cliente MCP, propuestas, orquestador (en dos pasadas: lectura, luego propuestas), y finalmente DTOs+rutas+app.

**Tech Stack:** Python ≥3.14, FastAPI, `pyjwt`, `mcp` SDK (cliente stdio), `a2ui-agent-sdk` (`a2ui.inference_formats.direct_json.DirectJsonFormat`, `a2ui.basic_catalog.provider.BasicCatalog`), `google-genai`, pytest + pytest-asyncio, `unittest.mock` para simular Gemini en tests (nunca se golpea la API real).

**Spec:** `docs/superpowers/specs/2026-09-11-me-alcanza-design.md`

## Global Constraints

- `requires-python = ">=3.14"` (ya en `pyproject.toml`).
- El LLM (Gemini) **nunca** ve `account_id` en ningún schema de tool — se inyecta siempre server-side desde el JWT.
- Las tools de mutación reales del MCP (`ejecutar_transferencia`, `crear_apartado`) **nunca** se declaran en el contexto de Gemini — solo las invoca el backend, y solo desde el manejo de confirmación de una propuesta ya validada.
- `autenticar` y `get_contacto` (nueva, ver Task 1) **tampoco** se declaran como tools de Gemini — `autenticar` es un "oráculo de credenciales" si se expone (hallazgo de la revisión final del plan del MCP server) y `get_contacto` es de uso interno del backend para resolver `contacto_id → cuenta_destino` con verificación de dueño.
- `proponer_transferencia` exige `contacto_id` (entero, resuelto vía `buscar_contacto`), nunca un nombre libre — el LLM no puede saltarse la desambiguación.
- El allowlist de tools que ve Gemini se define explícitamente en código (listas literales), nunca se deriva de `list_tools()` del MCP.
- Respuesta del backend al frontend: un JSON único por turno (sin streaming SSE) — fuera de alcance para este plan.
- Tests del orquestador **mockean** `genai_client` (nunca pegan a la API real de Gemini); las pruebas del cliente MCP y del servidor sí usan el MCP real (stdio), sin mocks.
- Usuarios demo: `ana`/`pass123` (account_id `"ana"`), `luis`/`pass456` (account_id `"luis"`) — mismos que en el MCP.

**Desviación consciente del spec:** el spec original pedía HTTP 409 para propuestas expiradas/inexistentes/ajenas en `/api/confirm-action`. Este plan, igual que la prueba anterior (que tampoco lo implementó pese a especificarlo), devuelve siempre `200` con un bloque A2UI de error — el frontend ya distingue el caso por el contenido del bloque, y separar el control de flujo por excepciones para variar solo el código HTTP no aporta valor de UX a cambio de la complejidad. Si en el futuro se necesita el código 409 real (ej. para telemetría/monitoreo), es un cambio aislado en `routes.py` sin tocar el orquestador.

---

### Task 1: Nueva tool `get_contacto` en el MCP (por id, con verificación de dueño)

**Contexto:** el MCP ya tiene `buscar_contacto(account_id, query)` (búsqueda por nombre/alias, puede ser ambigua). Para poder ejecutar una transferencia de forma segura después de que el usuario elige un contacto, el backend necesita resolver `contacto_id → cuenta_destino` verificando que ese contacto pertenezca a la cuenta que confirma — eso no existe todavía. Esta tool es de uso **interno del backend**, nunca se declara a Gemini.

**Files:**
- Modify: `src/me_alcanza/mcp_bank/db.py`
- Modify: `src/me_alcanza/mcp_bank/server.py`
- Modify: `tests/mcp_bank/test_db.py`
- Modify: `tests/mcp_bank/test_server.py`

**Interfaces:**
- Consumes: tabla `contactos` (ya existe).
- Produces: `db.get_contacto(conn, account_id: str, contacto_id: int) -> dict | None` (mismo shape que los resultados de `buscar_contacto`: `id, nombre, alias, cuenta_destino, relacion`). Tool MCP `get_contacto(account_id, contacto_id) -> dict`, que **lanza `ValueError`** si no existe o no pertenece a esa cuenta (mismo patrón que `get_saldo`/`get_cuenta` — nunca devuelve `None` al protocolo MCP).

- [ ] **Step 1: Escribir los tests de `db.get_contacto`**

```python
# agregar a tests/mcp_bank/test_db.py

def test_get_contacto_por_id(conn):
    contactos = db.buscar_contacto(conn, "ana", "pepe")
    contacto = db.get_contacto(conn, "ana", contactos[0]["id"])
    assert contacto == contactos[0]


def test_get_contacto_inexistente_devuelve_none(conn):
    assert db.get_contacto(conn, "ana", 999999) is None


def test_get_contacto_de_otra_cuenta_devuelve_none(conn):
    contactos = db.buscar_contacto(conn, "ana", "pepe")
    assert db.get_contacto(conn, "luis", contactos[0]["id"]) is None
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_db.py -v -k get_contacto`
Expected: FAIL — `AttributeError: module 'db' has no attribute 'get_contacto'`.

- [ ] **Step 3: Implementar `db.get_contacto`**

```python
# agregar a src/me_alcanza/mcp_bank/db.py

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
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_db.py -v -k get_contacto`
Expected: PASS (3 tests).

- [ ] **Step 5: Escribir el test de la tool MCP**

```python
# agregar a tests/mcp_bank/test_server.py

@pytest.mark.asyncio
async def test_mcp_server_get_contacto_por_id_y_error_si_no_pertenece(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with stdio_client(_params(db_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            contactos = await _call(session, "buscar_contacto", {"account_id": "ana", "query": "pepe"})
            contacto = await _call(
                session, "get_contacto", {"account_id": "ana", "contacto_id": contactos[0]["id"]}
            )
            assert contacto == contactos[0]

            result = await session.call_tool(
                "get_contacto", {"account_id": "luis", "contacto_id": contactos[0]["id"]}
            )
            assert result.is_error is True
```

Actualizar también `test_mcp_server_expone_las_tools_esperadas` para incluir `"get_contacto"` en el set esperado:

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
            }
```

- [ ] **Step 6: Correr los tests y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_server.py -v`
Expected: FAIL — `test_mcp_server_expone_las_tools_esperadas` falla (falta `get_contacto` en las tools reales) y el nuevo test falla con "Unknown tool".

- [ ] **Step 7: Implementar la tool MCP `get_contacto`**

```python
# agregar a src/me_alcanza/mcp_bank/server.py

@mcp.tool()
def get_contacto(account_id: str, contacto_id: int) -> dict:
    """Obtiene un contacto/beneficiario por id, verificando que pertenezca a la cuenta. Uso interno del backend, nunca se expone al LLM."""
    conn = _connection()
    try:
        resultado = db.get_contacto(conn, account_id, contacto_id)
        if resultado is None:
            raise ValueError(f"Contacto no encontrado para esta cuenta: {contacto_id}")
        return resultado
    finally:
        conn.close()
```

- [ ] **Step 8: Correr toda la suite del MCP y confirmar cero regresiones**

Run: `uv run pytest tests/mcp_bank/ -v`
Expected: PASS (32 anteriores + 3 nuevos en `test_db.py` + 1 nuevo en `test_server.py` = 36 tests).

- [ ] **Step 9: Commit**

```bash
git add src/me_alcanza/mcp_bank/db.py src/me_alcanza/mcp_bank/server.py tests/mcp_bank/test_db.py tests/mcp_bank/test_server.py
git commit -m "feat: add get_contacto MCP tool for secure contact_id resolution"
```

---

### Task 2: Scaffold del backend + autenticación JWT

**Files:**
- Create: `src/me_alcanza/backend/__init__.py`
- Create: `src/me_alcanza/backend/auth.py`
- Create: `tests/backend/__init__.py`
- Create: `tests/backend/test_auth.py`

**Interfaces:**
- Consumes: nada.
- Produces: `auth.create_token(account_id: str, secret: str, expires_minutes: int = 30) -> str`,
  `auth.decode_token(token: str, secret: str) -> str` (devuelve `account_id`, lanza excepciones de `jwt` si es inválido/expiró),
  `auth.get_current_account_id(request: fastapi.Request) -> str` (dependency de FastAPI: lee `Authorization: Bearer <token>` de `request.headers`, usa `request.app.state.jwt_secret`; lanza `HTTPException(401)` si falta el header o el token es inválido/expiró).

- [ ] **Step 1: Crear el paquete backend**

`src/me_alcanza/backend/__init__.py` — archivo vacío.
`tests/backend/__init__.py` — archivo vacío.

- [ ] **Step 2: Escribir los tests de auth**

```python
# tests/backend/test_auth.py
import jwt
import pytest
from fastapi import HTTPException, Request

from me_alcanza.backend import auth

SECRET = "test-secret-that-is-long-enough-for-pyjwt-hs256"


def test_create_and_decode_token_roundtrip():
    token = auth.create_token("ana", SECRET, expires_minutes=30)
    assert auth.decode_token(token, SECRET) == "ana"


def test_decode_token_expirado_lanza_error():
    token = auth.create_token("ana", SECRET, expires_minutes=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        auth.decode_token(token, SECRET)


def test_decode_token_secreto_incorrecto_lanza_error():
    token = auth.create_token("ana", SECRET, expires_minutes=30)
    with pytest.raises(jwt.InvalidTokenError):
        auth.decode_token(token, "otro-secreto-that-is-long-enough-for-pyjwt")


def _make_request(headers: dict, jwt_secret: str = SECRET) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "app": type("App", (), {"state": type("State", (), {"jwt_secret": jwt_secret})()})(),
    }
    return Request(scope)


def test_get_current_account_id_ok():
    token = auth.create_token("luis", SECRET)
    request = _make_request({"authorization": f"Bearer {token}"})
    assert auth.get_current_account_id(request) == "luis"


def test_get_current_account_id_sin_header_lanza_401():
    request = _make_request({})
    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_account_id(request)
    assert exc_info.value.status_code == 401


def test_get_current_account_id_token_invalido_lanza_401():
    request = _make_request({"authorization": "Bearer no-es-un-jwt"})
    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_account_id(request)
    assert exc_info.value.status_code == 401
```

- [ ] **Step 3: Correr los tests y verificar que fallan**

Run: `uv run pytest tests/backend/test_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'me_alcanza.backend.auth'`.

- [ ] **Step 4: Implementar `auth.py`**

```python
# src/me_alcanza/backend/auth.py
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, Request

ALGORITHM = "HS256"


def create_token(account_id: str, secret: str, expires_minutes: int = 30) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": account_id,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(token: str, secret: str) -> str:
    payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    return payload["sub"]


def get_current_account_id(request: Request) -> str:
    header = request.headers.get("authorization")
    if not header or not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Falta el header Authorization")

    token = header.removeprefix("Bearer ")
    try:
        return decode_token(token, request.app.state.jwt_secret)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
```

- [ ] **Step 5: Correr los tests y verificar que pasan**

Run: `uv run pytest tests/backend/test_auth.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add src/me_alcanza/backend/__init__.py src/me_alcanza/backend/auth.py tests/backend/__init__.py tests/backend/test_auth.py
git commit -m "feat: add JWT-based backend authentication"
```

---

### Task 3: Cliente del MCP (wrapper stdio con desempaquetado correcto del SDK)

**Contexto:** el MCP server ya construido serializa `str` y `list[...]` distinto de `dict` (hallazgo de la Task 6 del plan del MCP server): para `str`/`list[...]` hay que leer `result.structured_content` (envoltura `{"result": ...}`); para `dict` hay que parsear `result.content[0].text` como JSON. El wrapper debe manejar ambos casos — **no** copiar el patrón ingenuo `json.loads(result.content[0].text)` de la prueba anterior, que se rompe para `autenticar` (devuelve `str`) y para cualquier tool que devuelva una lista.

**Files:**
- Create: `src/me_alcanza/backend/mcp_client.py`
- Create: `tests/backend/test_mcp_client.py`

**Interfaces:**
- Consumes: `me_alcanza.mcp_bank.server` (el módulo ejecutable del MCP, ya construido).
- Produces: `mcp_client.connect_mcp(db_path: str) -> AsyncContextManager[ClientSession]`,
  `class BankMcpClient: def __init__(self, session: ClientSession)`,
  `async def call(self, tool_name: str, arguments: dict) -> Any` (lanza `RuntimeError` si `result.is_error`; si no, desempaqueta `structured_content` cuando existe — desenvolviendo `{"result": ...}` — o si no, parsea `content[0].text` como JSON).

- [ ] **Step 1: Escribir los tests del cliente MCP**

```python
# tests/backend/test_mcp_client.py
import pytest

from me_alcanza.backend.mcp_client import BankMcpClient, connect_mcp


@pytest.mark.asyncio
async def test_call_dict_result(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with connect_mcp(str(db_path)) as session:
        client = BankMcpClient(session)
        saldo = await client.call("get_saldo", {"account_id": "ana"})
        assert saldo == {"saldo": 500.00, "moneda": "MXN"}


@pytest.mark.asyncio
async def test_call_str_result(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with connect_mcp(str(db_path)) as session:
        client = BankMcpClient(session)
        account_id = await client.call("autenticar", {"username": "ana", "password": "pass123"})
        assert account_id == "ana"
        assert await client.call("autenticar", {"username": "ana", "password": "mala"}) is None


@pytest.mark.asyncio
async def test_call_list_result(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with connect_mcp(str(db_path)) as session:
        client = BankMcpClient(session)
        contactos = await client.call("buscar_contacto", {"account_id": "ana", "query": "pepe"})
        assert isinstance(contactos, list)
        assert len(contactos) == 2


@pytest.mark.asyncio
async def test_call_lanza_runtime_error_en_tool_error(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with connect_mcp(str(db_path)) as session:
        client = BankMcpClient(session)
        with pytest.raises(RuntimeError):
            await client.call("get_saldo", {"account_id": "fantasma"})
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `uv run pytest tests/backend/test_mcp_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'me_alcanza.backend.mcp_client'`.

- [ ] **Step 3: Implementar `mcp_client.py`**

```python
# src/me_alcanza/backend/mcp_client.py
import json
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class BankMcpClient:
    def __init__(self, session: ClientSession):
        self._session = session

    async def call(self, tool_name: str, arguments: dict) -> Any:
        result = await self._session.call_tool(tool_name, arguments)
        if result.is_error:
            raise RuntimeError(result.content[0].text)

        # El SDK instalado no siempre devuelve JSON en content[0].text: para
        # resultados str/list[...] usa structured_content = {"result": <valor>};
        # para dict, content[0].text sí es el JSON directo. Ver la nota
        # equivalente en tests/mcp_bank/test_server.py::_call.
        sc = result.structured_content
        if sc is not None:
            return sc["result"] if set(sc.keys()) == {"result"} else sc
        return json.loads(result.content[0].text)


@asynccontextmanager
async def connect_mcp(db_path: str) -> AsyncIterator[ClientSession]:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "me_alcanza.mcp_bank.server"],
        env={"BANK_DB_PATH": db_path},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `uv run pytest tests/backend/test_mcp_client.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/backend/mcp_client.py tests/backend/test_mcp_client.py
git commit -m "feat: add async MCP client wrapper with SDK-correct result unwrapping"
```

---

### Task 4: Contrato genérico de propuesta de acción

**Files:**
- Create: `src/me_alcanza/backend/proposals.py`
- Create: `tests/backend/test_proposals.py`

**Interfaces:**
- Consumes: nada (estructura de datos pura, en memoria de proceso).
- Produces: `@dataclass class Proposal: id: str; account_id: str; tipo: str; payload: dict; resumen: str; created_at: float`,
  `PROPOSALS: dict[str, Proposal]` (diccionario en memoria, TTL corto),
  `PROPOSAL_TTL_SECONDS: int = 300`,
  `crear_propuesta(account_id: str, tipo: str, payload: dict, resumen: str) -> Proposal`,
  `obtener_propuesta_valida(proposal_id: str, account_id: str) -> Proposal | None` (`None` si no existe, no pertenece a `account_id`, o expiró — en el caso de expirada, además la elimina de `PROPOSALS`),
  `descartar_propuesta(proposal_id: str) -> None`.

- [ ] **Step 1: Escribir los tests de propuestas**

```python
# tests/backend/test_proposals.py
import time

import pytest

from me_alcanza.backend import proposals


@pytest.fixture(autouse=True)
def _clear_proposals():
    proposals.PROPOSALS.clear()
    yield
    proposals.PROPOSALS.clear()


def test_crear_propuesta_genera_id_unico_y_la_guarda():
    p1 = proposals.crear_propuesta("ana", "apartado", {"meta_id": 1}, "Apartar $100")
    p2 = proposals.crear_propuesta("ana", "apartado", {"meta_id": 1}, "Apartar $100")
    assert p1.id != p2.id
    assert proposals.PROPOSALS[p1.id] is p1
    assert proposals.PROPOSALS[p2.id] is p2


def test_obtener_propuesta_valida_ok():
    p = proposals.crear_propuesta("ana", "transferencia", {"monto": 500}, "Transferir $500")
    assert proposals.obtener_propuesta_valida(p.id, "ana") is p


def test_obtener_propuesta_valida_cuenta_distinta_devuelve_none():
    p = proposals.crear_propuesta("ana", "transferencia", {"monto": 500}, "Transferir $500")
    assert proposals.obtener_propuesta_valida(p.id, "luis") is None
    # no se elimina solo por consultarla con otra cuenta
    assert p.id in proposals.PROPOSALS


def test_obtener_propuesta_valida_inexistente_devuelve_none():
    assert proposals.obtener_propuesta_valida("no-existe", "ana") is None


def test_obtener_propuesta_valida_expirada_devuelve_none_y_la_elimina():
    p = proposals.crear_propuesta("ana", "apartado", {"meta_id": 1}, "Apartar $100")
    p.created_at = time.time() - proposals.PROPOSAL_TTL_SECONDS - 1
    assert proposals.obtener_propuesta_valida(p.id, "ana") is None
    assert p.id not in proposals.PROPOSALS


def test_descartar_propuesta_la_elimina():
    p = proposals.crear_propuesta("ana", "apartado", {"meta_id": 1}, "Apartar $100")
    proposals.descartar_propuesta(p.id)
    assert p.id not in proposals.PROPOSALS


def test_descartar_propuesta_inexistente_no_lanza_error():
    proposals.descartar_propuesta("no-existe")
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `uv run pytest tests/backend/test_proposals.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'me_alcanza.backend.proposals'`.

- [ ] **Step 3: Implementar `proposals.py`**

```python
# src/me_alcanza/backend/proposals.py
import time
import uuid
from dataclasses import dataclass, field

PROPOSAL_TTL_SECONDS = 300


@dataclass
class Proposal:
    id: str
    account_id: str
    tipo: str
    payload: dict
    resumen: str
    created_at: float = field(default_factory=time.time)


PROPOSALS: dict[str, Proposal] = {}


def crear_propuesta(account_id: str, tipo: str, payload: dict, resumen: str) -> Proposal:
    proposal = Proposal(
        id=str(uuid.uuid4()),
        account_id=account_id,
        tipo=tipo,
        payload=payload,
        resumen=resumen,
    )
    PROPOSALS[proposal.id] = proposal
    return proposal


def obtener_propuesta_valida(proposal_id: str, account_id: str) -> Proposal | None:
    proposal = PROPOSALS.get(proposal_id)
    if proposal is None or proposal.account_id != account_id:
        return None
    if time.time() - proposal.created_at > PROPOSAL_TTL_SECONDS:
        PROPOSALS.pop(proposal_id, None)
        return None
    return proposal


def descartar_propuesta(proposal_id: str) -> None:
    PROPOSALS.pop(proposal_id, None)
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `uv run pytest tests/backend/test_proposals.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/backend/proposals.py tests/backend/test_proposals.py
git commit -m "feat: add generic action-proposal contract"
```

---

### Task 5: Orquestador — tools de lectura, prompt del sistema y `handle_message`

**Files:**
- Create: `src/me_alcanza/backend/orchestrator.py`
- Create: `tests/backend/test_orchestrator.py`

**Interfaces:**
- Consumes: `mcp_client.BankMcpClient` (Task 3, interfaz `async def call(tool_name, arguments) -> Any`).
- Produces: `error_a2ui_block(mensaje: str) -> list[dict]`,
  `read_only_tool_declarations() -> list[google.genai.types.Tool]`,
  `build_system_prompt() -> str`,
  `class Orchestrator: def __init__(self, genai_client, model: str, mcp_client: BankMcpClient)`,
  `async def handle_message(self, account_id: str, mensaje: str) -> list[dict]` (bloque A2UI final o bloque de error).
  Esta tarea cubre solo las tools de **lectura**; `proponer_transferencia`/`proponer_apartado`/`confirm_action` se agregan en la Task 6 (mismo archivo, se extiende).

- [ ] **Step 1: Escribir los tests de las tools de lectura y `handle_message`**

```python
# tests/backend/test_orchestrator.py
from unittest.mock import AsyncMock, MagicMock

import pytest
from google.genai import types

from me_alcanza.backend.orchestrator import Orchestrator, error_a2ui_block

CATALOG_ID = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"

SALDO_A2UI_RESPONSE = f'''Aquí está tu saldo:
<a2ui-json>
[
  {{"version": "v0.9", "createSurface": {{"surfaceId": "main", "catalogId": "{CATALOG_ID}"}}}},
  {{"version": "v0.9", "updateComponents": {{"surfaceId": "main", "components": [
    {{"id": "root", "component": "Card", "child": "txt"}},
    {{"id": "txt", "component": "Text", "text": {{"path": "/msg"}}}}
  ]}}}},
  {{"version": "v0.9", "updateDataModel": {{"surfaceId": "main", "path": "/", "value": {{"msg": "Tu saldo es $500.0 MXN"}}}}}}
]
</a2ui-json>
'''


def _mock_function_call_response(name: str, args: dict):
    call = types.FunctionCall(name=name, args=args)
    response = MagicMock()
    response.function_calls = [call]
    return response


def _mock_final_response(text: str):
    response = MagicMock()
    response.function_calls = []
    response.text = text
    return response


@pytest.mark.asyncio
async def test_handle_message_llama_mcp_con_account_id_inyectado():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(return_value={"saldo": 500.0, "moneda": "MXN"})

    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response("get_saldo", {}),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    messages = await orchestrator.handle_message("ana", "¿cuánto tengo?")

    mcp_client.call.assert_awaited_once_with("get_saldo", {"account_id": "ana"})
    assert messages[0]["createSurface"]["surfaceId"] == "main"


@pytest.mark.asyncio
async def test_handle_message_ignora_account_id_que_intente_inyectar_el_llm():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(return_value={"saldo": 500.0, "moneda": "MXN"})

    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response("get_saldo", {"account_id": "luis"}),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", "¿cuánto tengo?")

    mcp_client.call.assert_awaited_once_with("get_saldo", {"account_id": "ana"})


@pytest.mark.asyncio
async def test_handle_message_get_movimientos_reenvia_limit():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(return_value=[])

    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response("get_movimientos", {"limit": 3}),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", "mis últimos movimientos")

    mcp_client.call.assert_awaited_once_with("get_movimientos", {"account_id": "ana", "limit": 3})


@pytest.mark.asyncio
async def test_handle_message_simular_flujo_de_caja_reenvia_argumentos():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(
        return_value={
            "alcanza": False,
            "saldo_minimo_proyectado": 500.0,
            "fecha_critica": "2026-10-13",
            "margen": -570.0,
            "apartado_sugerido": {"monto_por_periodo": 142.5, "periodicidad": "semanal", "num_periodos": 4},
        }
    )

    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response(
                "simular_flujo_de_caja", {"fecha_objetivo": "2026-10-13", "monto_objetivo": 8000.0}
            ),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", "¿me alcanza para el concierto?")

    mcp_client.call.assert_awaited_once_with(
        "simular_flujo_de_caja",
        {"account_id": "ana", "fecha_objetivo": "2026-10-13", "monto_objetivo": 8000.0},
    )


@pytest.mark.asyncio
async def test_handle_message_buscar_contacto_reenvia_query():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(return_value=[{"id": 1, "nombre": "José Ramírez", "alias": "Pepe"}])

    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response("buscar_contacto", {"query": "pepe"}),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", "deposítale a pepe")

    mcp_client.call.assert_awaited_once_with("buscar_contacto", {"account_id": "ana", "query": "pepe"})


@pytest.mark.asyncio
async def test_handle_message_respuesta_no_valida_cae_a_bloque_de_error():
    mcp_client = MagicMock()
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_final_response("esto no tiene bloque a2ui"),
            _mock_final_response("tampoco esto"),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    messages = await orchestrator.handle_message("ana", "hola")

    assert messages == error_a2ui_block(messages[2]["updateDataModel"]["value"]["mensaje"])


@pytest.mark.asyncio
async def test_handle_message_error_esperado_del_mcp_se_devuelve_al_modelo_para_que_reintente():
    # Ej. el usuario pide una fecha_objetivo inválida para simular_flujo_de_caja:
    # el error debe llegar al modelo como function response (para que pida una
    # fecha válida en el siguiente turno de la conversación), no cortar todo
    # el mensaje con un bloque de error genérico.
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=RuntimeError("fecha_objetivo no puede ser anterior a hoy"))

    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response(
                "simular_flujo_de_caja", {"fecha_objetivo": "2020-01-01", "monto_objetivo": 100.0}
            ),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    messages = await orchestrator.handle_message("ana", "¿me alcanza para algo en 2020?")

    assert genai_client.models.generate_content.call_count == 2
    assert messages[0]["createSurface"]["surfaceId"] == "main"


@pytest.mark.asyncio
async def test_handle_message_excepcion_no_prevista_cae_a_bloque_de_error():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=KeyError("algo salió mal de forma inesperada"))

    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[_mock_function_call_response("get_saldo", {})]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    messages = await orchestrator.handle_message("ana", "¿cuánto tengo?")

    assert messages == error_a2ui_block(messages[2]["updateDataModel"]["value"]["mensaje"])
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `uv run pytest tests/backend/test_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'me_alcanza.backend.orchestrator'`.

- [ ] **Step 3: Implementar `orchestrator.py` (parte de lectura)**

```python
# src/me_alcanza/backend/orchestrator.py
from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.inference_formats.direct_json.format import DirectJsonFormat
from google.genai import types

from .mcp_client import BankMcpClient

_VERSION = "0.9"
_ALLOWED_COMPONENTS = ["Card", "Column", "Row", "Text", "Button", "List", "Divider"]
MAX_TOOL_CALL_ROUNDS = 5

_READ_ONLY_TOOLS = {
    "get_saldo",
    "get_cuenta",
    "get_movimientos",
    "get_ingresos_programados",
    "get_gastos_fijos",
    "get_metas",
    "buscar_contacto",
    "simular_flujo_de_caja",
}


def _catalog_id() -> str:
    return BasicCatalog.get_catalog_id(_VERSION)


def error_a2ui_block(mensaje: str) -> list[dict]:
    surface_id = "error"
    return [
        {
            "version": "v0.9",
            "createSurface": {"surfaceId": surface_id, "catalogId": _catalog_id()},
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": surface_id,
                "components": [
                    {"id": "root", "component": "Card", "child": "msg"},
                    {"id": "msg", "component": "Text", "text": {"path": "/mensaje"}},
                ],
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": surface_id,
                "path": "/",
                "value": {"mensaje": mensaje},
            },
        },
    ]


def _confirmation_a2ui_block(mensaje: str) -> list[dict]:
    surface_id = "confirmacion"
    return [
        {
            "version": "v0.9",
            "createSurface": {"surfaceId": surface_id, "catalogId": _catalog_id()},
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": surface_id,
                "components": [
                    {"id": "root", "component": "Card", "child": "msg"},
                    {"id": "msg", "component": "Text", "text": {"path": "/mensaje"}},
                ],
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": surface_id,
                "path": "/",
                "value": {"mensaje": mensaje},
            },
        },
    ]


def read_only_tool_declarations() -> list[types.Tool]:
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="get_saldo",
                    description="Obtiene el saldo y moneda de la cuenta del usuario actual.",
                    parameters=types.Schema(type=types.Type.OBJECT, properties={}),
                ),
                types.FunctionDeclaration(
                    name="get_cuenta",
                    description="Obtiene titular, número de cuenta y saldo de la cuenta del usuario actual.",
                    parameters=types.Schema(type=types.Type.OBJECT, properties={}),
                ),
                types.FunctionDeclaration(
                    name="get_movimientos",
                    description="Obtiene los movimientos más recientes de la cuenta del usuario actual.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "limit": types.Schema(
                                type=types.Type.INTEGER,
                                description="Cantidad máxima de movimientos a devolver.",
                            )
                        },
                    ),
                ),
                types.FunctionDeclaration(
                    name="get_ingresos_programados",
                    description="Obtiene los ingresos recurrentes programados (ej. nómina) de la cuenta del usuario actual.",
                    parameters=types.Schema(type=types.Type.OBJECT, properties={}),
                ),
                types.FunctionDeclaration(
                    name="get_gastos_fijos",
                    description="Obtiene los gastos fijos recurrentes (ej. renta, colegiaturas) de la cuenta del usuario actual.",
                    parameters=types.Schema(type=types.Type.OBJECT, properties={}),
                ),
                types.FunctionDeclaration(
                    name="get_metas",
                    description="Obtiene las metas de ahorro guardadas de la cuenta del usuario actual.",
                    parameters=types.Schema(type=types.Type.OBJECT, properties={}),
                ),
                types.FunctionDeclaration(
                    name="buscar_contacto",
                    description=(
                        "Busca contactos/beneficiarios de la cuenta del usuario actual por nombre "
                        "o apodo. Puede devolver varios resultados si el nombre es ambiguo."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={"query": types.Schema(type=types.Type.STRING)},
                        required=["query"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="simular_flujo_de_caja",
                    description=(
                        "Proyecta el flujo de caja de la cuenta del usuario actual entre hoy y "
                        "fecha_objetivo y determina si alcanza para monto_objetivo. Úsala SIEMPRE "
                        "para responder preguntas de tipo '¿me alcanza para...?'; nunca calcules "
                        "esto tú mismo."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "fecha_objetivo": types.Schema(
                                type=types.Type.STRING,
                                description="Fecha del gasto discrecional, formato YYYY-MM-DD.",
                            ),
                            "monto_objetivo": types.Schema(type=types.Type.NUMBER),
                        },
                        required=["fecha_objetivo", "monto_objetivo"],
                    ),
                ),
            ]
        )
    ]


def build_system_prompt() -> str:
    fmt = DirectJsonFormat(
        version=_VERSION, catalogs=[BasicCatalog.get_config(version=_VERSION)]
    )
    return fmt.prompt_generator.generate(
        role_description=(
            "Eres el asistente financiero de un banco. Ayudas a responder si a la persona le "
            "alcanza el dinero para un gasto futuro, dados sus ingresos y gastos programados, y "
            "puedes operar su cuenta (transferencias, apartados de ahorro). Respondes SIEMPRE "
            "generando una interfaz A2UI (nunca solo texto plano)."
        ),
        workflow_description=(
            "Para preguntas de tipo '¿me alcanza para...?' SIEMPRE llama a 'simular_flujo_de_caja' "
            "con la fecha objetivo y el monto; nunca calcules tú mismo el flujo de caja. Usa "
            "'get_ingresos_programados', 'get_gastos_fijos' y 'get_metas' para entender el contexto "
            "financiero antes de responder. Nunca inventes saldos, movimientos, ingresos, gastos ni "
            "metas: siempre usa el resultado real de las herramientas."
        ),
        allowed_components=_ALLOWED_COMPONENTS,
        include_schema=True,
    )


class Orchestrator:
    def __init__(self, genai_client, model: str, mcp_client: BankMcpClient):
        self._client = genai_client
        self._model = model
        self._mcp = mcp_client
        self._fmt = DirectJsonFormat(
            version=_VERSION, catalogs=[BasicCatalog.get_config(version=_VERSION)]
        )
        self._system_prompt = build_system_prompt()

    def _tool_declarations(self) -> list[types.Tool]:
        return read_only_tool_declarations()

    async def _run_tool_loop(self, account_id: str, contents: list) -> str:
        config = types.GenerateContentConfig(
            system_instruction=self._system_prompt,
            tools=self._tool_declarations(),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        for _ in range(MAX_TOOL_CALL_ROUNDS):
            response = self._client.models.generate_content(
                model=self._model, contents=contents, config=config
            )
            if not response.function_calls:
                return response.text

            contents.append(response.candidates[0].content)

            for call in response.function_calls:
                tool_result = await self._dispatch_tool_call(account_id, call)
                contents.append(
                    types.Part.from_function_response(name=call.name, response=tool_result)
                )

        return ""

    async def _dispatch_tool_call(self, account_id: str, call) -> dict:
        if call.name in _READ_ONLY_TOOLS:
            args = {"account_id": account_id}
            if call.name == "get_movimientos" and call.args and "limit" in call.args:
                args["limit"] = call.args["limit"]
            elif call.name == "buscar_contacto":
                args["query"] = call.args["query"]
            elif call.name == "simular_flujo_de_caja":
                args["fecha_objetivo"] = call.args["fecha_objetivo"]
                args["monto_objetivo"] = float(call.args["monto_objetivo"])
            try:
                return await self._mcp.call(call.name, args)
            except RuntimeError as exc:
                # Error esperado del MCP (ej. fecha inválida, cuenta inexistente):
                # se le devuelve al modelo como function response para que pueda
                # reaccionar (pedir datos válidos) en vez de cortar todo el turno.
                return {"error": str(exc)}
        return {"error": f"Herramienta no permitida: {call.name}"}

    async def handle_message(self, account_id: str, mensaje: str) -> list[dict]:
        contents = [mensaje]

        try:
            final_text = await self._run_tool_loop(account_id, contents)
        except Exception as exc:  # noqa: BLE001 - fallback controlado hacia UI de error
            return error_a2ui_block(f"Ocurrió un error al procesar tu solicitud: {exc}")

        for attempt in range(2):
            try:
                parts = self._fmt.parser.parse_response(final_text)
            except Exception as exc:  # noqa: BLE001
                if attempt == 1:
                    break
                contents.append(
                    f"Tu respuesta anterior no era un bloque A2UI válido: {exc}. Corrígela."
                )
                config = types.GenerateContentConfig(
                    system_instruction=self._system_prompt,
                    tools=self._tool_declarations(),
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                )
                response = self._client.models.generate_content(
                    model=self._model, contents=contents, config=config
                )
                final_text = response.text
                continue

            for part in parts:
                if part.a2ui_json:
                    return part.a2ui_json

            break

        return error_a2ui_block("No se pudo generar una respuesta válida. Intenta de nuevo.")
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `uv run pytest tests/backend/test_orchestrator.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/backend/orchestrator.py tests/backend/test_orchestrator.py
git commit -m "feat: add LLM orchestrator with read-only tool loop and A2UI parsing"
```

---

### Task 6: Orquestador — propuestas (transferencia, apartado) y confirmación

**Files:**
- Modify: `src/me_alcanza/backend/orchestrator.py`
- Modify: `tests/backend/test_orchestrator.py`

**Interfaces:**
- Consumes: `proposals.crear_propuesta`, `proposals.obtener_propuesta_valida`, `proposals.descartar_propuesta`, `proposals.PROPOSALS` (Task 4); tools MCP `get_contacto`, `ejecutar_transferencia`, `crear_apartado` (nunca declaradas a Gemini).
- Produces: extiende `Orchestrator` con `async def confirm_action(self, account_id: str, proposal_id: str) -> list[dict]`; agrega `proponer_transferencia` y `proponer_apartado` al tool-calling (sin declarar `ejecutar_transferencia`/`crear_apartado`/`get_contacto`/`autenticar` a Gemini).

- [ ] **Step 1: Escribir los tests de propuestas y confirmación**

```python
# agregar a tests/backend/test_orchestrator.py
from me_alcanza.backend import proposals


@pytest.fixture(autouse=True)
def _clear_proposals():
    proposals.PROPOSALS.clear()
    yield
    proposals.PROPOSALS.clear()


@pytest.mark.asyncio
async def test_handle_message_proponer_transferencia_resuelve_contacto_y_no_ejecuta_nada():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(
        return_value={"id": 1, "nombre": "José Ramírez", "alias": "Pepe", "cuenta_destino": "9988776655", "relacion": "hermano"}
    )

    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response(
                "proponer_transferencia", {"contacto_id": 1, "monto": 500.0, "concepto": "Renta"}
            ),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", "deposítale 500 a Pepe mi hermano")

    mcp_client.call.assert_awaited_once_with("get_contacto", {"account_id": "ana", "contacto_id": 1})
    assert len(proposals.PROPOSALS) == 1
    proposal = next(iter(proposals.PROPOSALS.values()))
    assert proposal.tipo == "transferencia"
    assert proposal.account_id == "ana"
    assert proposal.payload == {
        "contacto_id": 1,
        "destino_cuenta": "9988776655",
        "monto": 500.0,
        "concepto": "Renta",
    }


@pytest.mark.asyncio
async def test_handle_message_proponer_transferencia_contacto_inexistente_no_crea_propuesta():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=RuntimeError("Contacto no encontrado para esta cuenta: 999"))

    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response(
                "proponer_transferencia", {"contacto_id": 999, "monto": 500.0, "concepto": "x"}
            ),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", "deposítale a alguien que no existe")

    assert len(proposals.PROPOSALS) == 0


@pytest.mark.asyncio
async def test_handle_message_proponer_transferencia_monto_no_positivo_no_crea_propuesta():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock()

    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response(
                "proponer_transferencia", {"contacto_id": 1, "monto": -500.0, "concepto": "x"}
            ),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", "transfiere -500")

    mcp_client.call.assert_not_called()
    assert len(proposals.PROPOSALS) == 0


@pytest.mark.asyncio
async def test_handle_message_proponer_apartado_crea_propuesta_sin_tocar_mcp():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock()

    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response(
                "proponer_apartado",
                {"meta_id": 7, "monto_por_periodo": 142.5, "periodicidad": "semanal"},
            ),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", "activa el apartado")

    mcp_client.call.assert_not_called()
    assert len(proposals.PROPOSALS) == 1
    proposal = next(iter(proposals.PROPOSALS.values()))
    assert proposal.tipo == "apartado"
    assert proposal.payload == {"meta_id": 7, "monto_por_periodo": 142.5, "periodicidad": "semanal"}


@pytest.mark.asyncio
async def test_handle_message_proponer_apartado_monto_no_positivo_no_crea_propuesta():
    mcp_client = MagicMock()
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response(
                "proponer_apartado", {"meta_id": 7, "monto_por_periodo": 0, "periodicidad": "semanal"}
            ),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", "activa un apartado de 0")

    assert len(proposals.PROPOSALS) == 0


@pytest.mark.asyncio
async def test_confirm_action_apartado_llama_crear_apartado_en_mcp():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(return_value={"ok": True, "apartado": {"id": 1}})
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)

    proposal = proposals.crear_propuesta(
        "ana", "apartado", {"meta_id": 7, "monto_por_periodo": 142.5, "periodicidad": "semanal"}, "Apartar $142.50"
    )

    messages = await orchestrator.confirm_action("ana", proposal.id)

    mcp_client.call.assert_awaited_once_with(
        "crear_apartado",
        {"account_id": "ana", "meta_id": 7, "monto_por_periodo": 142.5, "periodicidad": "semanal"},
    )
    assert "createSurface" in messages[0]
    assert proposal.id not in proposals.PROPOSALS


@pytest.mark.asyncio
async def test_confirm_action_transferencia_revalida_contacto_y_ejecuta():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(
        side_effect=[
            {"id": 1, "nombre": "José Ramírez", "cuenta_destino": "9988776655"},  # get_contacto (revalidación)
            {"ok": True, "nuevo_saldo": 358.0, "movimiento": {}},  # ejecutar_transferencia
        ]
    )
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)

    proposal = proposals.crear_propuesta(
        "ana",
        "transferencia",
        {"contacto_id": 1, "destino_cuenta": "9988776655", "monto": 142.5, "concepto": "Regalo"},
        "Transferir $142.50 a José Ramírez",
    )

    messages = await orchestrator.confirm_action("ana", proposal.id)

    assert mcp_client.call.await_args_list[0].args == ("get_contacto", {"account_id": "ana", "contacto_id": 1})
    assert mcp_client.call.await_args_list[1].args == (
        "ejecutar_transferencia",
        {"origen_id": "ana", "destino_cuenta": "9988776655", "monto": 142.5, "concepto": "Regalo"},
    )
    assert "createSurface" in messages[0]


@pytest.mark.asyncio
async def test_confirm_action_transferencia_contacto_ya_no_existe_cae_a_error():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=RuntimeError("Contacto no encontrado para esta cuenta: 1"))
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)

    proposal = proposals.crear_propuesta(
        "ana",
        "transferencia",
        {"contacto_id": 1, "destino_cuenta": "9988776655", "monto": 100.0, "concepto": "x"},
        "Transferir $100",
    )

    messages = await orchestrator.confirm_action("ana", proposal.id)

    assert messages == error_a2ui_block(messages[2]["updateDataModel"]["value"]["mensaje"])
    assert proposal.id not in proposals.PROPOSALS


@pytest.mark.asyncio
async def test_confirm_action_propuesta_inexistente_o_ajena_cae_a_error():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock()
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)

    messages = await orchestrator.confirm_action("ana", "no-existe")

    mcp_client.call.assert_not_called()
    assert messages == error_a2ui_block(messages[2]["updateDataModel"]["value"]["mensaje"])
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `uv run pytest tests/backend/test_orchestrator.py -v`
Expected: FAIL en los 9 tests nuevos — `proponer_transferencia`/`proponer_apartado`/`confirm_action` no existen todavía.

- [ ] **Step 3: Extender `orchestrator.py` con propuestas y confirmación**

```python
# modificar src/me_alcanza/backend/orchestrator.py

# agregar el import al inicio del archivo:
from . import proposals

# reemplazar la función read_only_tool_declarations() por esta versión ampliada
# (agrega proponer_transferencia y proponer_apartado al final de la lista de
# function_declarations, sin quitar ninguna de las ya existentes):

def read_only_tool_declarations() -> list[types.Tool]:
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="get_saldo",
                    description="Obtiene el saldo y moneda de la cuenta del usuario actual.",
                    parameters=types.Schema(type=types.Type.OBJECT, properties={}),
                ),
                types.FunctionDeclaration(
                    name="get_cuenta",
                    description="Obtiene titular, número de cuenta y saldo de la cuenta del usuario actual.",
                    parameters=types.Schema(type=types.Type.OBJECT, properties={}),
                ),
                types.FunctionDeclaration(
                    name="get_movimientos",
                    description="Obtiene los movimientos más recientes de la cuenta del usuario actual.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "limit": types.Schema(
                                type=types.Type.INTEGER,
                                description="Cantidad máxima de movimientos a devolver.",
                            )
                        },
                    ),
                ),
                types.FunctionDeclaration(
                    name="get_ingresos_programados",
                    description="Obtiene los ingresos recurrentes programados (ej. nómina) de la cuenta del usuario actual.",
                    parameters=types.Schema(type=types.Type.OBJECT, properties={}),
                ),
                types.FunctionDeclaration(
                    name="get_gastos_fijos",
                    description="Obtiene los gastos fijos recurrentes (ej. renta, colegiaturas) de la cuenta del usuario actual.",
                    parameters=types.Schema(type=types.Type.OBJECT, properties={}),
                ),
                types.FunctionDeclaration(
                    name="get_metas",
                    description="Obtiene las metas de ahorro guardadas de la cuenta del usuario actual.",
                    parameters=types.Schema(type=types.Type.OBJECT, properties={}),
                ),
                types.FunctionDeclaration(
                    name="buscar_contacto",
                    description=(
                        "Busca contactos/beneficiarios de la cuenta del usuario actual por nombre "
                        "o apodo. Puede devolver varios resultados si el nombre es ambiguo."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={"query": types.Schema(type=types.Type.STRING)},
                        required=["query"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="simular_flujo_de_caja",
                    description=(
                        "Proyecta el flujo de caja de la cuenta del usuario actual entre hoy y "
                        "fecha_objetivo y determina si alcanza para monto_objetivo. Úsala SIEMPRE "
                        "para responder preguntas de tipo '¿me alcanza para...?'; nunca calcules "
                        "esto tú mismo."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "fecha_objetivo": types.Schema(
                                type=types.Type.STRING,
                                description="Fecha del gasto discrecional, formato YYYY-MM-DD.",
                            ),
                            "monto_objetivo": types.Schema(type=types.Type.NUMBER),
                        },
                        required=["fecha_objetivo", "monto_objetivo"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="proponer_transferencia",
                    description=(
                        "Propone una transferencia a un contacto YA IDENTIFICADO por su id exacto "
                        "(nunca por nombre libre — primero usa 'buscar_contacto'; si hay más de un "
                        "resultado, pide al usuario que elija antes de llamar esta herramienta). "
                        "NO ejecuta la transferencia: solo genera una propuesta que el usuario debe "
                        "confirmar explícitamente en la UI."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "contacto_id": types.Schema(type=types.Type.INTEGER),
                            "monto": types.Schema(type=types.Type.NUMBER),
                            "concepto": types.Schema(type=types.Type.STRING),
                        },
                        required=["contacto_id", "monto", "concepto"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="proponer_apartado",
                    description=(
                        "Propone crear un apartado de ahorro hacia una meta existente (obtenida con "
                        "'get_metas'). NO lo ejecuta: solo genera una propuesta que el usuario debe "
                        "confirmar explícitamente en la UI."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "meta_id": types.Schema(type=types.Type.INTEGER),
                            "monto_por_periodo": types.Schema(type=types.Type.NUMBER),
                            "periodicidad": types.Schema(type=types.Type.STRING),
                        },
                        required=["meta_id", "monto_por_periodo", "periodicidad"],
                    ),
                ),
            ]
        )
    ]


# reemplazar el método _dispatch_tool_call de la clase Orchestrator por esta versión:

    async def _dispatch_tool_call(self, account_id: str, call) -> dict:
        if call.name in _READ_ONLY_TOOLS:
            args = {"account_id": account_id}
            if call.name == "get_movimientos" and call.args and "limit" in call.args:
                args["limit"] = call.args["limit"]
            elif call.name == "buscar_contacto":
                args["query"] = call.args["query"]
            elif call.name == "simular_flujo_de_caja":
                args["fecha_objetivo"] = call.args["fecha_objetivo"]
                args["monto_objetivo"] = float(call.args["monto_objetivo"])
            try:
                return await self._mcp.call(call.name, args)
            except RuntimeError as exc:
                return {"error": str(exc)}

        if call.name == "proponer_transferencia":
            return await self._proponer_transferencia(account_id, call.args)

        if call.name == "proponer_apartado":
            return self._proponer_apartado(account_id, call.args)

        return {"error": f"Herramienta no permitida: {call.name}"}

    async def _proponer_transferencia(self, account_id: str, args: dict) -> dict:
        monto = float(args["monto"])
        if monto <= 0:
            return {"error": "El monto debe ser mayor a cero"}

        contacto_id = int(args["contacto_id"])
        try:
            contacto = await self._mcp.call(
                "get_contacto", {"account_id": account_id, "contacto_id": contacto_id}
            )
        except RuntimeError:
            return {"error": "No se encontró ese contacto para tu cuenta"}

        proposal = proposals.crear_propuesta(
            account_id=account_id,
            tipo="transferencia",
            payload={
                "contacto_id": contacto_id,
                "destino_cuenta": contacto["cuenta_destino"],
                "monto": monto,
                "concepto": args["concepto"],
            },
            resumen=f"Transferir ${monto:.2f} a {contacto['nombre']}",
        )
        return {"proposalId": proposal.id, "resumen": proposal.resumen}

    def _proponer_apartado(self, account_id: str, args: dict) -> dict:
        monto_por_periodo = float(args["monto_por_periodo"])
        if monto_por_periodo <= 0:
            return {"error": "monto_por_periodo debe ser mayor a cero"}

        proposal = proposals.crear_propuesta(
            account_id=account_id,
            tipo="apartado",
            payload={
                "meta_id": int(args["meta_id"]),
                "monto_por_periodo": monto_por_periodo,
                "periodicidad": args["periodicidad"],
            },
            resumen=f"Apartar ${monto_por_periodo:.2f} {args['periodicidad']} hacia tu meta",
        )
        return {"proposalId": proposal.id, "resumen": proposal.resumen}

    async def confirm_action(self, account_id: str, proposal_id: str) -> list[dict]:
        proposal = proposals.obtener_propuesta_valida(proposal_id, account_id)
        if proposal is None:
            return error_a2ui_block(
                "La propuesta no existe, no te pertenece, o expiró. Pídela de nuevo."
            )

        try:
            if proposal.tipo == "apartado":
                await self._mcp.call(
                    "crear_apartado",
                    {
                        "account_id": account_id,
                        "meta_id": proposal.payload["meta_id"],
                        "monto_por_periodo": proposal.payload["monto_por_periodo"],
                        "periodicidad": proposal.payload["periodicidad"],
                    },
                )
                return _confirmation_a2ui_block("Apartado de ahorro activado correctamente.")

            if proposal.tipo == "transferencia":
                try:
                    contacto = await self._mcp.call(
                        "get_contacto",
                        {"account_id": account_id, "contacto_id": proposal.payload["contacto_id"]},
                    )
                except RuntimeError:
                    return error_a2ui_block("El contacto de esta propuesta ya no existe.")

                resultado = await self._mcp.call(
                    "ejecutar_transferencia",
                    {
                        "origen_id": account_id,
                        "destino_cuenta": contacto["cuenta_destino"],
                        "monto": proposal.payload["monto"],
                        "concepto": proposal.payload["concepto"],
                    },
                )
                return _confirmation_a2ui_block(
                    f"Transferencia realizada. Nuevo saldo: ${resultado['nuevo_saldo']:.2f}"
                )

            return error_a2ui_block(f"Tipo de propuesta desconocido: {proposal.tipo}")
        except Exception as exc:  # noqa: BLE001 - fallback controlado hacia UI de error
            return error_a2ui_block(f"No se pudo completar la acción: {exc}")
        finally:
            proposals.descartar_propuesta(proposal_id)
```

**Nota para quien implemente:** el `_dispatch_tool_call` y `read_only_tool_declarations()` de la Task 5 se **reemplazan por completo** por las versiones de este Step 3 (no se agregan como funciones duplicadas). El resto de `orchestrator.py` (imports existentes, `error_a2ui_block`, `_confirmation_a2ui_block`, `_run_tool_loop`, `handle_message`, `__init__`) no cambia — **excepto `build_system_prompt()`**, que también se reemplaza por la versión del Step 3.1 a continuación, porque la Task 5 no le enseñaba nada al modelo sobre proponer/confirmar acciones ni sobre desambiguar contactos (esa guía no puede vivir solo en la descripción de la tool — el modelo necesita instrucciones de flujo explícitas).

- [ ] **Step 3.1: Reemplazar `build_system_prompt()` para incluir el flujo de propuesta/confirmación y la desambiguación**

```python
# reemplaza la función build_system_prompt() completa en src/me_alcanza/backend/orchestrator.py

def build_system_prompt() -> str:
    fmt = DirectJsonFormat(
        version=_VERSION, catalogs=[BasicCatalog.get_config(version=_VERSION)]
    )
    return fmt.prompt_generator.generate(
        role_description=(
            "Eres el asistente financiero de un banco. Ayudas a responder si a la persona le "
            "alcanza el dinero para un gasto futuro, dados sus ingresos y gastos programados, y "
            "puedes operar su cuenta (transferencias, apartados de ahorro). Respondes SIEMPRE "
            "generando una interfaz A2UI (nunca solo texto plano)."
        ),
        workflow_description=(
            "Para preguntas de tipo '¿me alcanza para...?' SIEMPRE llama a 'simular_flujo_de_caja' "
            "con la fecha objetivo y el monto; nunca calcules tú mismo el flujo de caja. Usa "
            "'get_ingresos_programados', 'get_gastos_fijos' y 'get_metas' para entender el contexto "
            "financiero antes de responder. Si el resultado de 'simular_flujo_de_caja' indica que no "
            "alcanza, usa el campo 'apartado_sugerido' para proponer un apartado con "
            "'proponer_apartado' (usando el meta_id de 'get_metas'), y muestra una tarjeta con un "
            "botón cuya acción sea el evento 'confirmar_accion' con context={'proposalId': "
            "'<el id que te devolvió la herramienta>'}. Para transferencias, primero llama a "
            "'buscar_contacto' con el nombre que mencione el usuario; si el resultado tiene más de "
            "un contacto, MUESTRA una lista de selección en la UI (no adivines) y espera a que el "
            "usuario elija antes de continuar. Ya con un contacto exacto, usa "
            "'proponer_transferencia' con su id y muestra una tarjeta de confirmación con un botón "
            "cuya acción sea el evento 'confirmar_accion' con context={'proposalId': '<el id>'}. "
            "Nunca afirmes que una transferencia o un apartado ya se realizó: solo se ejecutan "
            "cuando el usuario confirma explícitamente. Nunca inventes saldos, movimientos, "
            "ingresos, gastos, metas o contactos: siempre usa el resultado real de las herramientas."
        ),
        allowed_components=_ALLOWED_COMPONENTS,
        include_schema=True,
    )
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `uv run pytest tests/backend/test_orchestrator.py -v`
Expected: PASS (17 tests en total).

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/backend/orchestrator.py tests/backend/test_orchestrator.py
git commit -m "feat: add transfer and savings-pocket proposal/confirmation flow"
```

---

### Task 7: DTOs, rutas, app y punto de entrada

**Files:**
- Create: `src/me_alcanza/backend/dtos.py`
- Create: `src/me_alcanza/backend/routes.py`
- Create: `src/me_alcanza/backend/app.py`
- Create: `src/me_alcanza/main.py`
- Create: `tests/backend/test_routes.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `auth` (Task 2), `mcp_client.connect_mcp`/`BankMcpClient` (Task 3), `orchestrator.Orchestrator` (Tasks 5-6).
- Produces: `create_app(genai_client, model: str, jwt_secret: str, db_path: str) -> FastAPI`; rutas `POST /api/login`, `POST /api/chat`, `POST /api/confirm-action`; comando `uv run me-alcanza` que levanta el backend completo en `0.0.0.0:8000`.

**Nota sobre TDD en esta tarea:** `dtos.py`, `routes.py` y `app.py` son tres archivos mutuamente dependientes — `routes.py` no es probable de forma aislada sin `app.py` armando el `TestClient` (mismo patrón que la prueba anterior: no existe un `test_dtos.py` ni un `test_routes.py` que no pase por `create_app`). Por eso aquí se escriben los tres archivos primero (Steps 1-3) y los tests que ejercitan el conjunto completo después (Step 4) — no hay un estado "rojo" significativo intermedio como en las tareas anteriores.

- [ ] **Step 1: Crear los DTOs**

```python
# src/me_alcanza/backend/dtos.py
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str


class ChatRequest(BaseModel):
    mensaje: str


class ChatResponse(BaseModel):
    a2ui_messages: list[dict]


class ConfirmActionRequest(BaseModel):
    proposal_id: str


class ConfirmActionResponse(BaseModel):
    a2ui_messages: list[dict]
```

- [ ] **Step 2: Crear las rutas**

```python
# src/me_alcanza/backend/routes.py
from fastapi import APIRouter, Depends, HTTPException, Request

from . import auth
from .dtos import (
    ChatRequest,
    ChatResponse,
    ConfirmActionRequest,
    ConfirmActionResponse,
    LoginRequest,
    LoginResponse,
)

router = APIRouter(prefix="/api")


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request) -> LoginResponse:
    account_id = await request.app.state.mcp_client.call(
        "autenticar", {"username": payload.username, "password": payload.password}
    )
    if account_id is None:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    token = auth.create_token(account_id, request.app.state.jwt_secret)
    return LoginResponse(token=token)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> ChatResponse:
    messages = await request.app.state.orchestrator.handle_message(account_id, payload.mensaje)
    return ChatResponse(a2ui_messages=messages)


@router.post("/confirm-action", response_model=ConfirmActionResponse)
async def confirm_action(
    payload: ConfirmActionRequest,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> ConfirmActionResponse:
    messages = await request.app.state.orchestrator.confirm_action(account_id, payload.proposal_id)
    return ConfirmActionResponse(a2ui_messages=messages)
```

- [ ] **Step 3: Crear `app.py`**

```python
# src/me_alcanza/backend/app.py
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .mcp_client import BankMcpClient, connect_mcp
from .orchestrator import Orchestrator
from .routes import router


def create_app(genai_client, model: str, jwt_secret: str, db_path: str) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with connect_mcp(db_path) as session:
            app.state.mcp_client = BankMcpClient(session)
            app.state.orchestrator = Orchestrator(genai_client, model, app.state.mcp_client)
            app.state.jwt_secret = jwt_secret
            yield

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app
```

- [ ] **Step 4: Escribir los tests de rutas (vía `TestClient`, sin golpear Gemini real)**

```python
# tests/backend/test_routes.py
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from me_alcanza.backend.app import create_app
from me_alcanza.backend import proposals


@pytest.fixture(autouse=True)
def _clear_proposals():
    proposals.PROPOSALS.clear()
    yield
    proposals.PROPOSALS.clear()


@pytest.fixture
def app(tmp_path):
    genai_client = MagicMock()
    return create_app(
        genai_client=genai_client,
        model="gemini-test",
        jwt_secret="test-secret-that-is-long-enough-for-pyjwt-hs256",
        db_path=str(tmp_path / "test_banco.db"),
    )


def test_login_credenciales_correctas_devuelve_token(app):
    with TestClient(app) as client:
        response = client.post("/api/login", json={"username": "ana", "password": "pass123"})
        assert response.status_code == 200
        assert "token" in response.json()


def test_login_credenciales_incorrectas_devuelve_401(app):
    with TestClient(app) as client:
        response = client.post("/api/login", json={"username": "ana", "password": "mala"})
        assert response.status_code == 401


def test_chat_sin_token_devuelve_401(app):
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"mensaje": "hola"})
        assert response.status_code == 401


def test_chat_con_token_llama_al_orquestador(app):
    with TestClient(app) as client:
        login = client.post("/api/login", json={"username": "ana", "password": "pass123"})
        token = login.json()["token"]

        fake_messages = [{"version": "v0.9", "createSurface": {"surfaceId": "main", "catalogId": "x"}}]
        app.state.orchestrator.handle_message = AsyncMock(return_value=fake_messages)

        response = client.post(
            "/api/chat",
            json={"mensaje": "¿me alcanza para el concierto?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json() == {"a2ui_messages": fake_messages}
        app.state.orchestrator.handle_message.assert_awaited_once_with("ana", "¿me alcanza para el concierto?")


def test_confirm_action_sin_token_devuelve_401(app):
    with TestClient(app) as client:
        response = client.post("/api/confirm-action", json={"proposal_id": "x"})
        assert response.status_code == 401


def test_confirm_action_con_token_llama_al_orquestador(app):
    with TestClient(app) as client:
        login = client.post("/api/login", json={"username": "ana", "password": "pass123"})
        token = login.json()["token"]

        fake_messages = [{"version": "v0.9", "createSurface": {"surfaceId": "confirmacion", "catalogId": "x"}}]
        app.state.orchestrator.confirm_action = AsyncMock(return_value=fake_messages)

        response = client.post(
            "/api/confirm-action",
            json={"proposal_id": "prop-1"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json() == {"a2ui_messages": fake_messages}
        app.state.orchestrator.confirm_action.assert_awaited_once_with("ana", "prop-1")
```

- [ ] **Step 5: Correr los tests y verificar que pasan**

Run: `uv run pytest tests/backend/test_routes.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Crear el punto de entrada `main.py`**

```python
# src/me_alcanza/main.py
import os

import uvicorn
from dotenv import load_dotenv
from google import genai

from me_alcanza.backend.app import create_app

load_dotenv()


def main():
    genai_client = genai.Client(api_key=os.environ["GOOGLE_AI_STUDIO_API_KEY"])
    app = create_app(
        genai_client=genai_client,
        model=os.environ["GEMINI_MODEL"],
        jwt_secret=os.environ["JWT_SECRET"],
        db_path=os.environ.get("BANK_DB_PATH", "banco.db"),
    )
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Registrar el script en `pyproject.toml`**

Agregar esta sección justo después de `[project.optional-dependencies]` (antes de `[build-system]`):

```toml
[project.scripts]
me-alcanza = "me_alcanza.main:main"
```

- [ ] **Step 8: Verificar que el backend arranca de punta a punta (smoke test manual)**

Con un `.env` real en la raíz (`GOOGLE_AI_STUDIO_API_KEY`, `GEMINI_MODEL=gemini-3.6-flash`, `JWT_SECRET`, `BANK_DB_PATH=banco.db`):

Run: `uv run me-alcanza`
Expected: el proceso arranca sin excepciones, `uvicorn` reporta que escucha en `0.0.0.0:8000` (Ctrl+C para detener). No hace falta probar un mensaje de chat real todavía — eso se prueba manualmente cuando exista un frontend o con `curl`/`httpie` directo, fuera del alcance TDD de este plan.

- [ ] **Step 9: Correr toda la suite del backend y confirmar cero regresiones**

Run: `uv run pytest tests/ -v`
Expected: PASS (36 del MCP tras la Task 1 + los del backend: 6 auth + 4 mcp_client + 7 proposals + 17 orchestrator + 6 routes = 40 nuevos del backend). Total esperado: 36 + 40 = 76 tests, todos en verde.

- [ ] **Step 10: Commit**

```bash
git add src/me_alcanza/backend/dtos.py src/me_alcanza/backend/routes.py src/me_alcanza/backend/app.py src/me_alcanza/main.py tests/backend/test_routes.py pyproject.toml
git commit -m "feat: wire FastAPI app with login/chat/confirm-action routes and entrypoint"
```

---

## Qué sigue

Con este plan, `me-alcanza` tiene un backend completo y probado (auth, orquestación LLM↔MCP, contrato de propuesta/confirmación para apartados y transferencias con desambiguación) que se puede levantar con `uv run me-alcanza` y probar por HTTP. Los siguientes dos planes (pendientes de escribir) son los frontends — React (`@a2ui/react`, ruta crítica) y Flutter (`genui_a2ui`, secundario) — ambos consumiendo esta misma API sin cambios.
