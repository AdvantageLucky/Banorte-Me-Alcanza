# Hilos de chat + modo offline — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** El chat gana memoria real entre turnos vía hilos de conversación persistentes, y un modo offline determinista sirve de fallback automático cuando Gemini falla (cuota, red, sin API key).

**Architecture:** Conversaciones y mensajes viven detrás de MCP (mismo patrón que todo lo demás: el backend nunca toca SQLite directo). `Orchestrator.handle_message` reconstruye `contents` desde el historial persistido usando `types.Content(role=, parts=)` — API ya verificada contra la librería real instalada. Un módulo `fake_provider.py` nuevo da respuestas deterministas por keyword, usado tanto para forzar modo offline (`LLM_PROVIDER=fake`) como de fallback automático si la llamada real a Gemini lanza cualquier excepción.

**Tech Stack:** Mismo stack existente. Sin dependencias nuevas.

**Spec:** `docs/superpowers/specs/2026-09-12-hilos-chat-modo-offline-design.md`

## Global Constraints

- Conversaciones/mensajes se gestionan SIEMPRE vía tools MCP, nunca SQL directo desde `backend/`.
- `ChatRequest.conversacion_id` es opcional — si no se manda, `routes.py` crea una conversación nueva ANTES de llamar a `handle_message`, que por lo tanto SIEMPRE recibe un `conversacion_id` válido (nunca `None`) — la lógica de "crear si falta" vive en la ruta, no en el orquestador.
- El modo offline nunca fantasea con ser una respuesta real: el texto generado dice explícitamente que es una respuesta de modo offline/temporal.
- El fallback automático a offline se intenta SOLO cuando la llamada real a Gemini falla — nunca reemplaza silenciosamente una respuesta exitosa.
- TDD en todo. Sin cambios a `frontend/`/`flutter_app/` (este plan es 100% backend). Sin atribución IA en commits.

---

### Task 1: `db.py` — tablas `conversaciones`/`mensajes_conversacion` + CRUD

**Files:**
- Modify: `src/me_alcanza/mcp_bank/db.py`
- Test: `tests/mcp_bank/test_db.py`

**Interfaces:**
- Produces: `crear_conversacion(conn, account_id, titulo) -> dict`, `listar_conversaciones(conn, account_id) -> list[dict]`, `obtener_mensajes_conversacion(conn, account_id, conversacion_id) -> list[dict]`, `agregar_mensaje_conversacion(conn, account_id, conversacion_id, rol, contenido) -> None`, `eliminar_conversacion(conn, account_id, conversacion_id) -> None` — consumidos por Task 2.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/mcp_bank/test_db.py`:

```python
def test_crear_conversacion_y_listar(conn):
    conversacion = db.crear_conversacion(conn, "ana", "Mi primera conversación")
    assert conversacion["titulo"] == "Mi primera conversación"
    listado = db.listar_conversaciones(conn, "ana")
    assert len(listado) == 1
    assert listado[0]["id"] == conversacion["id"]


def test_listar_conversaciones_no_mezcla_cuentas(conn):
    db.crear_conversacion(conn, "ana", "x")
    assert db.listar_conversaciones(conn, "luis") == []


def test_agregar_y_obtener_mensajes_en_orden(conn):
    conversacion = db.crear_conversacion(conn, "ana", "x")
    db.agregar_mensaje_conversacion(conn, "ana", conversacion["id"], "user", "hola")
    db.agregar_mensaje_conversacion(conn, "ana", conversacion["id"], "model", "hola, ¿en qué te ayudo?")
    mensajes = db.obtener_mensajes_conversacion(conn, "ana", conversacion["id"])
    assert [m["rol"] for m in mensajes] == ["user", "model"]
    assert mensajes[0]["contenido"] == "hola"


def test_agregar_mensaje_a_conversacion_de_otra_cuenta_falla(conn):
    conversacion = db.crear_conversacion(conn, "ana", "x")
    with pytest.raises(ValueError):
        db.agregar_mensaje_conversacion(conn, "luis", conversacion["id"], "user", "hola")


def test_obtener_mensajes_de_conversacion_inexistente_falla(conn):
    with pytest.raises(ValueError):
        db.obtener_mensajes_conversacion(conn, "ana", 999999)


def test_eliminar_conversacion_borra_sus_mensajes(conn):
    conversacion = db.crear_conversacion(conn, "ana", "x")
    db.agregar_mensaje_conversacion(conn, "ana", conversacion["id"], "user", "hola")
    db.eliminar_conversacion(conn, "ana", conversacion["id"])
    assert db.listar_conversaciones(conn, "ana") == []
    with pytest.raises(ValueError):
        db.obtener_mensajes_conversacion(conn, "ana", conversacion["id"])


def test_eliminar_conversacion_de_otra_cuenta_falla(conn):
    conversacion = db.crear_conversacion(conn, "ana", "x")
    with pytest.raises(ValueError):
        db.eliminar_conversacion(conn, "luis", conversacion["id"])
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_db.py -k conversacion -v`
Expected: FAIL — `AttributeError`.

- [ ] **Step 3: Implementar en `src/me_alcanza/mcp_bank/db.py`**

3a. Agregar al `SCHEMA` (dentro del bloque de `CREATE TABLE IF NOT EXISTS`, después de `sugerencias` si ese plan ya se ejecutó, o después de `contactos` si no):

```sql
CREATE TABLE IF NOT EXISTS conversaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL REFERENCES usuarios(account_id),
    titulo TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mensajes_conversacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversacion_id INTEGER NOT NULL REFERENCES conversaciones(id),
    rol TEXT NOT NULL,
    contenido TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

3b. Agregar al final del archivo:

```python
def crear_conversacion(conn: sqlite3.Connection, account_id: str, titulo: str) -> dict:
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.execute(
        "INSERT INTO conversaciones (account_id, titulo, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (account_id, titulo, ahora, ahora),
    )
    conn.commit()
    return {"id": cursor.lastrowid, "titulo": titulo, "created_at": ahora, "updated_at": ahora}


def listar_conversaciones(conn: sqlite3.Connection, account_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, titulo, created_at, updated_at FROM conversaciones
        WHERE account_id = ? ORDER BY updated_at DESC
        """,
        (account_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _verificar_conversacion(conn: sqlite3.Connection, account_id: str, conversacion_id: int) -> None:
    row = conn.execute(
        "SELECT id FROM conversaciones WHERE id = ? AND account_id = ?", (conversacion_id, account_id)
    ).fetchone()
    if row is None:
        raise ValueError(f"Conversación no encontrada para esta cuenta: {conversacion_id}")


def obtener_mensajes_conversacion(conn: sqlite3.Connection, account_id: str, conversacion_id: int) -> list[dict]:
    _verificar_conversacion(conn, account_id, conversacion_id)
    rows = conn.execute(
        """
        SELECT rol, contenido, created_at FROM mensajes_conversacion
        WHERE conversacion_id = ? ORDER BY id ASC
        """,
        (conversacion_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def agregar_mensaje_conversacion(
    conn: sqlite3.Connection, account_id: str, conversacion_id: int, rol: str, contenido: str
) -> None:
    _verificar_conversacion(conn, account_id, conversacion_id)
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO mensajes_conversacion (conversacion_id, rol, contenido, created_at) VALUES (?, ?, ?, ?)",
        (conversacion_id, rol, contenido, ahora),
    )
    conn.execute("UPDATE conversaciones SET updated_at = ? WHERE id = ?", (ahora, conversacion_id))
    conn.commit()


def eliminar_conversacion(conn: sqlite3.Connection, account_id: str, conversacion_id: int) -> None:
    _verificar_conversacion(conn, account_id, conversacion_id)
    conn.execute("DELETE FROM mensajes_conversacion WHERE conversacion_id = ?", (conversacion_id,))
    conn.execute("DELETE FROM conversaciones WHERE id = ? AND account_id = ?", (conversacion_id, account_id))
    conn.commit()
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_db.py -v`
Expected: PASS — todos.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/mcp_bank/db.py tests/mcp_bank/test_db.py
git commit -m "feat: add conversaciones/mensajes_conversacion tables and CRUD"
```

---

### Task 2: `server.py` — exponer conversaciones vía MCP

**Files:**
- Modify: `src/me_alcanza/mcp_bank/server.py`
- Test: `tests/mcp_bank/test_server.py`

**Interfaces:**
- Consumes: funciones de `db.py` de la Task 1.
- Produces: tools MCP `crear_conversacion`, `listar_conversaciones`, `obtener_mensajes_conversacion`, `agregar_mensaje_conversacion`, `eliminar_conversacion` — consumidas por Task 3 (orquestador) y Task 8 (rutas REST).

- [ ] **Step 1: Actualizar el test del set exacto de tools + agregar test de integración**

En `tests/mcp_bank/test_server.py`, agregar las 5 tools nuevas al set esperado de `test_mcp_server_expone_las_tools_esperadas`.

Agregar al final del archivo:

```python
@pytest.mark.asyncio
async def test_mcp_server_conversaciones_flujo_completo(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with stdio_client(_params(db_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            conversacion = await _call(session, "crear_conversacion", {"account_id": "ana", "titulo": "x"})
            await _call(
                session,
                "agregar_mensaje_conversacion",
                {"account_id": "ana", "conversacion_id": conversacion["id"], "rol": "user", "contenido": "hola"},
            )
            mensajes = await _call(
                session, "obtener_mensajes_conversacion", {"account_id": "ana", "conversacion_id": conversacion["id"]}
            )
            assert len(mensajes) == 1
            listado = await _call(session, "listar_conversaciones", {"account_id": "ana"})
            assert len(listado) == 1
            resultado = await session.call_tool(
                "eliminar_conversacion", {"account_id": "ana", "conversacion_id": conversacion["id"]}
            )
            assert resultado.is_error is False
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/mcp_bank/test_server.py -v`
Expected: FAIL — tool-set incompleto, tools nuevas no existen.

- [ ] **Step 3: Implementar en `src/me_alcanza/mcp_bank/server.py`**

Agregar al final del archivo (antes de `if __name__ == "__main__":`):

```python
@mcp.tool()
def crear_conversacion(account_id: str, titulo: str) -> dict:
    """Crea un hilo de conversación nuevo para la cuenta del usuario."""
    conn = _connection()
    try:
        return db.crear_conversacion(conn, account_id, titulo)
    finally:
        conn.close()


@mcp.tool()
def listar_conversaciones(account_id: str) -> list[dict]:
    """Lista los hilos de conversación de la cuenta del usuario, más recientes primero."""
    conn = _connection()
    try:
        return db.listar_conversaciones(conn, account_id)
    finally:
        conn.close()


@mcp.tool()
def obtener_mensajes_conversacion(account_id: str, conversacion_id: int) -> list[dict]:
    """Obtiene el historial de mensajes de un hilo de conversación, en orden cronológico."""
    conn = _connection()
    try:
        return db.obtener_mensajes_conversacion(conn, account_id, conversacion_id)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    finally:
        conn.close()


@mcp.tool()
def agregar_mensaje_conversacion(account_id: str, conversacion_id: int, rol: str, contenido: str) -> dict:
    """Agrega un mensaje ('user' o 'model') al historial de un hilo de conversación."""
    conn = _connection()
    try:
        db.agregar_mensaje_conversacion(conn, account_id, conversacion_id, rol, contenido)
        return {"ok": True}
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    finally:
        conn.close()


@mcp.tool()
def eliminar_conversacion(account_id: str, conversacion_id: int) -> dict:
    """Elimina un hilo de conversación y todos sus mensajes."""
    conn = _connection()
    try:
        db.eliminar_conversacion(conn, account_id, conversacion_id)
        return {"ok": True}
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    finally:
        conn.close()
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/mcp_bank/test_server.py -v`
Expected: PASS — todos.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/mcp_bank/server.py tests/mcp_bank/test_server.py
git commit -m "feat: expose conversaciones CRUD via MCP server"
```

---

### Task 3: `fake_provider.py` — respuestas deterministas de modo offline

**Files:**
- Create: `src/me_alcanza/backend/fake_provider.py`
- Test: `tests/backend/test_fake_provider.py`

**Interfaces:**
- Consumes: nada.
- Produces: `generar_respuesta_offline(mensaje: str) -> str` — texto en el mismo formato `<a2ui-json>...</a2ui-json>` que produce Gemini. Consumido por Task 4.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/backend/test_fake_provider.py`:

```python
import json
import re

from me_alcanza.backend import fake_provider


def _extraer_a2ui(texto: str) -> list[dict]:
    match = re.search(r"<a2ui-json>(.*?)</a2ui-json>", texto, re.DOTALL)
    assert match is not None, "la respuesta offline debe traer un bloque <a2ui-json>"
    return json.loads(match.group(1))


def test_saldo_devuelve_tarjeta_de_saldo():
    texto = fake_provider.generar_respuesta_offline("¿cuál es mi saldo?")
    bloques = _extraer_a2ui(texto)
    assert any("createSurface" in b for b in bloques)
    valores = next(b for b in bloques if "updateDataModel" in b)["updateDataModel"]["value"]
    assert "offline" in json.dumps(valores).lower()


def test_meta_devuelve_tarjeta_de_metas():
    texto = fake_provider.generar_respuesta_offline("quiero ver mis metas de ahorro")
    bloques = _extraer_a2ui(texto)
    assert any("createSurface" in b for b in bloques)


def test_mensaje_generico_sin_keyword_conocida():
    texto = fake_provider.generar_respuesta_offline("cuéntame un chiste")
    bloques = _extraer_a2ui(texto)
    valores = next(b for b in bloques if "updateDataModel" in b)["updateDataModel"]["value"]
    assert "offline" in json.dumps(valores).lower()
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/backend/test_fake_provider.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `src/me_alcanza/backend/fake_provider.py`**

```python
import json

_CATALOG_ID = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"
_SURFACE_ID = "modo-offline"


def _bloque(mensaje: str) -> str:
    a2ui = [
        {"version": "v0.9", "createSurface": {"surfaceId": _SURFACE_ID, "catalogId": _CATALOG_ID}},
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": _SURFACE_ID,
                "components": [
                    {"id": "root", "component": "Card", "child": "col"},
                    {"id": "col", "component": "Column", "children": ["titulo", "msg"]},
                    {"id": "titulo", "component": "Text", "text": "Modo offline", "variant": "h3"},
                    {"id": "msg", "component": "Text", "text": {"path": "/mensaje"}},
                ],
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {"surfaceId": _SURFACE_ID, "path": "/", "value": {"mensaje": mensaje}},
        },
    ]
    return f"<a2ui-json>\n{json.dumps(a2ui)}\n</a2ui-json>"


def generar_respuesta_offline(mensaje: str) -> str:
    texto = mensaje.lower()
    if "saldo" in texto:
        return _bloque(
            "Modo offline: no puedo consultar tu saldo real en este momento. "
            "Este es un dato de ejemplo, no tu saldo verdadero."
        )
    if "meta" in texto or "ahorro" in texto:
        return _bloque(
            "Modo offline: no puedo consultar tus metas reales en este momento. "
            "Intenta de nuevo cuando el servicio esté disponible."
        )
    return _bloque(
        "Estamos en modo offline temporalmente y no podemos procesar tu solicitud ahora mismo. "
        "Intenta de nuevo en unos momentos."
    )
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/backend/test_fake_provider.py -v`
Expected: PASS — todos.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/backend/fake_provider.py tests/backend/test_fake_provider.py
git commit -m "feat: add deterministic offline provider for chat fallback"
```

---

### Task 4: `orchestrator.py` — `handle_message` multi-turno + fallback a modo offline

**Files:**
- Modify: `src/me_alcanza/backend/orchestrator.py`
- Test: `tests/backend/test_orchestrator.py`

**Interfaces:**
- Consumes: tools MCP `obtener_mensajes_conversacion`/`agregar_mensaje_conversacion` (Task 2), `fake_provider.generar_respuesta_offline` (Task 3).
- Produces: `Orchestrator(genai_client, model, mcp_client, provider="gemini")`, `handle_message(account_id, conversacion_id, mensaje)` — firma nueva, consumida por Task 8.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/backend/test_orchestrator.py`:

```python
@pytest.mark.asyncio
async def test_handle_message_carga_historial_y_construye_contents_con_roles():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(
        side_effect=[
            [{"rol": "user", "contenido": "hola"}, {"rol": "model", "contenido": "hola, ¿en qué te ayudo?"}],
            None,  # agregar_mensaje_conversacion (mensaje del usuario)
            None,  # agregar_mensaje_conversacion (respuesta del modelo)
        ]
    )
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(side_effect=[_mock_final_response(SALDO_A2UI_RESPONSE)])

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", 1, "¿cuánto tengo?")

    mcp_client.call.assert_any_call("obtener_mensajes_conversacion", {"account_id": "ana", "conversacion_id": 1})
    llamada_generate = genai_client.models.generate_content.call_args
    contents_enviados = llamada_generate.kwargs["contents"]
    # 2 mensajes de historial + 1 mensaje nuevo = 3 Content antes de correr el tool loop
    assert len(contents_enviados) == 3
    assert contents_enviados[0].role == "user"
    assert contents_enviados[1].role == "model"
    assert contents_enviados[2].role == "user"


@pytest.mark.asyncio
async def test_handle_message_persiste_el_turno_completo():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], None, None])
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(side_effect=[_mock_final_response(SALDO_A2UI_RESPONSE)])

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", 5, "hola")

    llamadas_guardado = [
        c for c in mcp_client.call.call_args_list if c.args[0] == "agregar_mensaje_conversacion"
    ]
    assert len(llamadas_guardado) == 2
    assert llamadas_guardado[0].args[1]["rol"] == "user"
    assert llamadas_guardado[0].args[1]["contenido"] == "hola"
    assert llamadas_guardado[1].args[1]["rol"] == "model"


@pytest.mark.asyncio
async def test_handle_message_hace_fallback_a_modo_offline_si_gemini_falla():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], None, None])
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(side_effect=RuntimeError("429 cuota agotada"))

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    messages = await orchestrator.handle_message("ana", 1, "¿cuál es mi saldo?")

    assert "createSurface" in messages[0]
    valores = next(m for m in messages if "updateDataModel" in m)["updateDataModel"]["value"]
    assert "offline" in str(valores).lower()
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/backend/test_orchestrator.py -k "carga_historial or persiste_el_turno or fallback_a_modo_offline" -v`
Expected: FAIL — `handle_message()` no acepta `conversacion_id` todavía.

- [ ] **Step 3: Implementar en `src/me_alcanza/backend/orchestrator.py`**

3a. Agregar el import al inicio del archivo:

```python
from . import fake_provider, proposals
```

(reemplaza la línea existente `from . import proposals`.)

3b. Cambiar `Orchestrator.__init__` para aceptar el provider:

```python
class Orchestrator:
    def __init__(self, genai_client, model: str, mcp_client: BankMcpClient, provider: str = "gemini"):
        self._client = genai_client
        self._model = model
        self._mcp = mcp_client
        self._provider = provider
        self._fmt = DirectJsonFormat(
            version=_VERSION, catalogs=[BasicCatalog.get_config(version=_VERSION)]
        )
        self._system_prompt = build_system_prompt()
```

3c. Reemplazar todo el método `handle_message` por:

```python
    async def handle_message(self, account_id: str, conversacion_id: int, mensaje: str) -> list[dict]:
        historial = await self._mcp.call(
            "obtener_mensajes_conversacion", {"account_id": account_id, "conversacion_id": conversacion_id}
        )
        contents = [
            types.Content(role=m["rol"], parts=[types.Part.from_text(text=m["contenido"])])
            for m in historial
        ]
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=mensaje)]))

        # Todo el flujo (tool loop + el reintento de auto-corrección de abajo) vive
        # bajo un único try/except: una excepción en CUALQUIER punto -incluyendo la
        # llamada a generate_content del reintento- debe caer al bloque de error,
        # nunca propagarse cruda fuera de handle_message.
        try:
            if self._provider == "fake":
                final_text = fake_provider.generar_respuesta_offline(mensaje)
            else:
                final_text = await self._run_tool_loop(account_id, contents)

            for attempt in range(2):
                try:
                    parts = self._fmt.parser.parse_response(final_text)
                except Exception as exc:  # noqa: BLE001
                    if attempt == 1:
                        break
                    contents.append(
                        f"Tu respuesta anterior no era un bloque A2UI válido: {exc}. Corrígela."
                    )
                    config = self._generate_content_config()
                    response = self._client.models.generate_content(
                        model=self._model, contents=contents, config=config
                    )
                    final_text = response.text
                    continue

                for part in parts:
                    if part.a2ui_json:
                        await self._mcp.call(
                            "agregar_mensaje_conversacion",
                            {
                                "account_id": account_id,
                                "conversacion_id": conversacion_id,
                                "rol": "user",
                                "contenido": mensaje,
                            },
                        )
                        await self._mcp.call(
                            "agregar_mensaje_conversacion",
                            {
                                "account_id": account_id,
                                "conversacion_id": conversacion_id,
                                "rol": "model",
                                "contenido": final_text,
                            },
                        )
                        return _rewrite_surface_id(part.a2ui_json, _new_surface_id())

                break
        except Exception:  # noqa: BLE001 - intenta modo offline antes de rendirse
            _logger.exception("handle_message falló de forma inesperada, intentando modo offline")
            if self._provider != "fake":
                try:
                    final_text = fake_provider.generar_respuesta_offline(mensaje)
                    parts = self._fmt.parser.parse_response(final_text)
                    for part in parts:
                        if part.a2ui_json:
                            return _rewrite_surface_id(part.a2ui_json, _new_surface_id())
                except Exception:  # noqa: BLE001
                    _logger.exception("el fallback a modo offline también falló")
            return error_a2ui_block(
                "Ocurrió un error al procesar tu solicitud. Intenta de nuevo en unos momentos."
            )

        return error_a2ui_block(
            "No se pudo generar una respuesta válida. Intenta de nuevo."
        )
```

Nota: se elimina el guardado del turno en el camino de fallback offline (no se
persiste una respuesta de modo offline como si fuera un turno real del
historial) — es intencional, evita que una respuesta genérica de emergencia
contamine el contexto de conversaciones futuras.

- [ ] **Step 4: Correr y verificar que pasan**

Run: `uv run pytest tests/backend/test_orchestrator.py -v`
Expected: PASS — todos. Revisa que ningún test viejo de `handle_message` siga llamándolo con la firma vieja (2 argumentos) — si alguno lo hace, actualízalo para pasar un `conversacion_id` (usa `1` como valor de prueba) y ajusta el mock de `mcp_client.call` para que devuelva `[]` en la primera llamada (historial vacío) antes del resto de sus `side_effect` ya existentes.

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/backend/orchestrator.py tests/backend/test_orchestrator.py
git commit -m "feat: give handle_message conversation memory and offline fallback"
```

---

### Task 5: `main.py` — configurar `LLM_PROVIDER` y detectar "sin proveedor"

**Files:**
- Modify: `src/me_alcanza/main.py`
- Modify: `src/me_alcanza/backend/app.py`

**Interfaces:**
- Consumes: `Orchestrator(..., provider=...)` (Task 4).
- Produces: arranque del backend que nunca falla por falta de API key.

- [ ] **Step 1: Verificar el comportamiento actual (no hay test automatizado aquí — es configuración de arranque)**

Leer `src/me_alcanza/main.py` y `src/me_alcanza/backend/app.py` tal como están hoy antes de tocarlos, para no romper el flujo de `create_app` que ya reciben las Tasks/tests de `test_routes.py` (el fixture `app` de esos tests construye `create_app` directo, sin pasar por `main.py` — verificar que `create_app` siga aceptando los mismos parámetros con un nuevo parámetro opcional, para no romper esos tests existentes).

- [ ] **Step 2: Implementar en `src/me_alcanza/main.py`**

```python
import logging
import os

import uvicorn
from dotenv import load_dotenv
from google import genai

from me_alcanza.backend.app import create_app

load_dotenv()

_logger = logging.getLogger(__name__)


def main():
    provider = os.environ.get("LLM_PROVIDER", "gemini")
    api_key = os.environ.get("GOOGLE_AI_STUDIO_API_KEY")
    if provider != "fake" and not api_key:
        _logger.warning(
            "GOOGLE_AI_STUDIO_API_KEY no está configurada — forzando LLM_PROVIDER=fake "
            "(modo offline) para que el backend arranque de todas formas."
        )
        provider = "fake"

    genai_client = genai.Client(api_key=api_key or "sin-configurar")
    app = create_app(
        genai_client=genai_client,
        model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
        jwt_secret=os.environ["JWT_SECRET"],
        db_path=os.environ.get("BANK_DB_PATH", "banco.db"),
        provider=provider,
    )
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Implementar en `src/me_alcanza/backend/app.py`**

`create_app` gana un parámetro `provider: str = "gemini"` que se reenvía al `Orchestrator`:

```python
def create_app(genai_client, model: str, jwt_secret: str, db_path: str, provider: str = "gemini") -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with connect_mcp(db_path) as session:
            app.state.mcp_client = BankMcpClient(session)
            app.state.orchestrator = Orchestrator(genai_client, model, app.state.mcp_client, provider=provider)
            app.state.jwt_secret = jwt_secret
            yield
```

(Solo cambia la línea de `Orchestrator(...)` dentro de `lifespan` y la firma de `create_app` — el resto del archivo queda igual.)

- [ ] **Step 4: Correr toda la suite para confirmar que nada se rompió**

Run: `uv run pytest tests/ -v`
Expected: PASS — todos (el parámetro `provider` tiene default `"gemini"`, así que los tests existentes que llaman `create_app` sin ese argumento siguen funcionando igual).

- [ ] **Step 5: Commit**

```bash
git add src/me_alcanza/main.py src/me_alcanza/backend/app.py
git commit -m "feat: configure LLM_PROVIDER and fall back to offline mode without an API key"
```

---

### Task 6: DTOs de conversaciones + `ChatRequest.conversacion_id`

**Files:**
- Modify: `src/me_alcanza/backend/dtos.py`

**Interfaces:**
- Produces: `ConversacionResponse`, `MensajeResponse`, `CrearConversacionRequest`, `ChatRequest` actualizado — consumidos por Task 7.

- [ ] **Step 1: Implementar en `src/me_alcanza/backend/dtos.py`**

Modificar `ChatRequest` (agregar el campo, sin quitar `mensaje`):

```python
class ChatRequest(BaseModel):
    mensaje: str
    conversacion_id: int | None = None
```

Agregar al final del archivo:

```python
class ConversacionResponse(BaseModel):
    id: int
    titulo: str
    created_at: str
    updated_at: str


class MensajeResponse(BaseModel):
    rol: str
    contenido: str
    created_at: str


class CrearConversacionRequest(BaseModel):
    titulo: str | None = None
```

- [ ] **Step 2: Verificar que importa sin errores**

Run: `uv run python3 -c "from me_alcanza.backend import dtos"`
Expected: sin salida, sin excepción.

- [ ] **Step 3: Commit**

```bash
git add src/me_alcanza/backend/dtos.py
git commit -m "feat: add conversacion DTOs and optional conversacion_id on ChatRequest"
```

---

### Task 7: Rutas REST de conversaciones + actualizar `/api/chat`

**Files:**
- Modify: `src/me_alcanza/backend/routes.py`
- Test: `tests/backend/test_routes.py`

**Interfaces:**
- Consumes: DTOs de Task 6; tools MCP de Task 2; `handle_message(account_id, conversacion_id, mensaje)` (Task 4).
- Produces: `GET/POST /api/conversaciones`, `GET /api/conversaciones/{id}/mensajes`, `DELETE /api/conversaciones/{id}`; `/api/chat` acepta `conversacion_id` opcional.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/backend/test_routes.py`:

```python
def test_chat_sin_conversacion_id_crea_una_automaticamente(app):
    with TestClient(app) as client:
        token = _login(client)
        fake_messages = [{"version": "v0.9", "createSurface": {"surfaceId": "x", "catalogId": "y"}}]
        app.state.orchestrator.handle_message = AsyncMock(return_value=fake_messages)
        response = client.post(
            "/api/chat", json={"mensaje": "hola"}, headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        app.state.orchestrator.handle_message.assert_awaited_once()
        args = app.state.orchestrator.handle_message.await_args.args
        assert args[0] == "ana"
        assert isinstance(args[1], int)  # se autogeneró un conversacion_id real
        assert args[2] == "hola"


def test_chat_con_conversacion_id_lo_reenvia_tal_cual(app):
    with TestClient(app) as client:
        token = _login(client)
        fake_messages = [{"version": "v0.9", "createSurface": {"surfaceId": "x", "catalogId": "y"}}]
        app.state.orchestrator.handle_message = AsyncMock(return_value=fake_messages)
        creada = client.post(
            "/api/conversaciones", json={}, headers={"Authorization": f"Bearer {token}"}
        ).json()
        response = client.post(
            "/api/chat",
            json={"mensaje": "hola", "conversacion_id": creada["id"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        args = app.state.orchestrator.handle_message.await_args.args
        assert args[1] == creada["id"]


def test_crear_conversacion_titulo_por_defecto(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.post("/api/conversaciones", json={}, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 201
        assert response.json()["titulo"] == "Nueva conversación"


def test_listar_conversaciones(app):
    with TestClient(app) as client:
        token = _login(client)
        client.post("/api/conversaciones", json={"titulo": "Uno"}, headers={"Authorization": f"Bearer {token}"})
        response = client.get("/api/conversaciones", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert len(response.json()) == 1


def test_obtener_mensajes_de_conversacion(app):
    with TestClient(app) as client:
        token = _login(client)
        creada = client.post(
            "/api/conversaciones", json={}, headers={"Authorization": f"Bearer {token}"}
        ).json()
        response = client.get(
            f"/api/conversaciones/{creada['id']}/mensajes", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json() == []


def test_eliminar_conversacion(app):
    with TestClient(app) as client:
        token = _login(client)
        creada = client.post(
            "/api/conversaciones", json={}, headers={"Authorization": f"Bearer {token}"}
        ).json()
        response = client.delete(
            f"/api/conversaciones/{creada['id']}", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 204
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `uv run pytest tests/backend/test_routes.py -k conversacion -v`
Expected: FAIL — 404 Not Found / `handle_message` firma vieja.

- [ ] **Step 3: Implementar en `src/me_alcanza/backend/routes.py`**

Actualizar el import de `.dtos` agregando `ConversacionResponse`, `CrearConversacionRequest`, `MensajeResponse`.

Reemplazar la ruta `chat` existente por:

```python
@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> ChatResponse:
    conversacion_id = payload.conversacion_id
    if conversacion_id is None:
        nueva = await request.app.state.mcp_client.call(
            "crear_conversacion", {"account_id": account_id, "titulo": payload.mensaje[:60]}
        )
        conversacion_id = nueva["id"]

    messages = await request.app.state.orchestrator.handle_message(
        account_id, conversacion_id, payload.mensaje
    )
    return ChatResponse(a2ui_messages=messages)
```

Agregar al final del archivo:

```python
@router.get("/conversaciones", response_model=list[ConversacionResponse])
async def list_conversaciones(
    request: Request, account_id: str = Depends(auth.get_current_account_id)
) -> list[ConversacionResponse]:
    try:
        conversaciones = await request.app.state.mcp_client.call(
            "listar_conversaciones", {"account_id": account_id}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [ConversacionResponse(**c) for c in conversaciones]


@router.post("/conversaciones", response_model=ConversacionResponse, status_code=201)
async def create_conversacion(
    payload: CrearConversacionRequest,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> ConversacionResponse:
    titulo = payload.titulo or "Nueva conversación"
    try:
        conversacion = await request.app.state.mcp_client.call(
            "crear_conversacion", {"account_id": account_id, "titulo": titulo}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ConversacionResponse(**conversacion)


@router.get("/conversaciones/{conversacion_id}/mensajes", response_model=list[MensajeResponse])
async def get_mensajes_conversacion(
    conversacion_id: int,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> list[MensajeResponse]:
    try:
        mensajes = await request.app.state.mcp_client.call(
            "obtener_mensajes_conversacion", {"account_id": account_id, "conversacion_id": conversacion_id}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [MensajeResponse(**m) for m in mensajes]


@router.delete("/conversaciones/{conversacion_id}", status_code=204)
async def delete_conversacion(
    conversacion_id: int,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> None:
    try:
        await request.app.state.mcp_client.call(
            "eliminar_conversacion", {"account_id": account_id, "conversacion_id": conversacion_id}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

- [ ] **Step 4: Correr y verificar que pasan, incluyendo los tests viejos de `/api/chat`**

Run: `uv run pytest tests/backend/test_routes.py -v`
Expected: PASS — todos. Los tests viejos `test_chat_sin_token_devuelve_401` y `test_chat_con_token_llama_al_orquestador` mockeaban `handle_message` con la firma vieja de 2 argumentos (`assert_awaited_once_with("ana", "¿me alcanza...?")`) — actualízalos para reflejar la firma nueva de 3 argumentos, verificando solo que el primer y tercer argumento posicional sean los esperados (el segundo, `conversacion_id`, es autogenerado y no se puede predecir su valor exacto en el test).

- [ ] **Step 5: Correr toda la suite**

Run: `uv run pytest tests/ -v`
Expected: PASS — todos los tests del proyecto.

- [ ] **Step 6: Commit**

```bash
git add src/me_alcanza/backend/routes.py tests/backend/test_routes.py
git commit -m "feat: add REST endpoints for conversaciones and wire conversacion_id into /api/chat"
```
