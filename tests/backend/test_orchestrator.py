from unittest.mock import AsyncMock, MagicMock

import pytest
from google.genai import types

from me_alcanza.backend import a2ui_custom_catalog, proposals
from me_alcanza.backend.orchestrator import (
    Orchestrator,
    _new_surface_id,
    _rewrite_surface_id,
    build_system_prompt,
    error_a2ui_block,
    read_only_tool_declarations,
)


@pytest.fixture(autouse=True)
def _clear_proposals():
    proposals.PROPOSALS.clear()
    yield
    proposals.PROPOSALS.clear()

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


SALDO_SIN_ROOT_A2UI_RESPONSE = f'''Aquí está tu saldo:
<a2ui-json>
[
  {{"version": "v0.9", "createSurface": {{"surfaceId": "main", "catalogId": "{CATALOG_ID}"}}}},
  {{"version": "v0.9", "updateComponents": {{"surfaceId": "main", "components": [
    {{"id": "tarjeta", "component": "Card", "child": "txt"}},
    {{"id": "txt", "component": "Text", "text": {{"path": "/msg"}}}}
  ]}}}},
  {{"version": "v0.9", "updateDataModel": {{"surfaceId": "main", "path": "/", "value": {{"msg": "Tu saldo es $500.0 MXN"}}}}}}
]
</a2ui-json>
'''


def test_new_surface_id_es_unico_cada_vez():
    assert _new_surface_id() != _new_surface_id()


def test_rewrite_surface_id_sobrescribe_los_tres_tipos_de_mensaje():
    original = [
        {"version": "v0.9", "createSurface": {"surfaceId": "lo-que-sea", "catalogId": "x"}},
        {
            "version": "v0.9",
            "updateComponents": {"surfaceId": "otro-distinto", "components": [{"id": "root"}]},
        },
        {
            "version": "v0.9",
            "updateDataModel": {"surfaceId": "tercero", "path": "/", "value": {"msg": "hola"}},
        },
    ]

    rewritten = _rewrite_surface_id(original, "turno-fijo")

    assert rewritten[0]["createSurface"]["surfaceId"] == "turno-fijo"
    assert rewritten[1]["updateComponents"]["surfaceId"] == "turno-fijo"
    assert rewritten[2]["updateDataModel"]["surfaceId"] == "turno-fijo"
    # No muta la lista original.
    assert original[0]["createSurface"]["surfaceId"] == "lo-que-sea"


def test_rewrite_surface_id_tambien_fuerza_el_catalogId_del_createSurface():
    # El modelo a veces alucina el catalogId del catálogo básico genérico de
    # la especificación (el que conoce de su entrenamiento) en vez del propio
    # del equipo: si eso llega tal cual al frontend, el MessageProcessor no
    # encuentra ese catálogo registrado (solo tiene el propio) y truena con
    # "Catalog not found", lo que el usuario ve como "No se pudo enviar el
    # mensaje" aunque la respuesta haya llegado bien por HTTP. Igual que con
    # surfaceId, no se confía en que el modelo elija el catalogId correcto.
    original = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "lo-que-sea",
                "catalogId": "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json",
            },
        },
    ]

    rewritten = _rewrite_surface_id(original, "turno-fijo")

    assert rewritten[0]["createSurface"]["catalogId"] == a2ui_custom_catalog.CUSTOM_CATALOG_ID


@pytest.mark.asyncio
async def test_handle_message_cada_turno_tiene_su_propia_superficie_unica():
    mcp_client = MagicMock()

    async def fake_call(name, args=None):
        if name == "obtener_mensajes_conversacion":
            return []
        return {"saldo": 500.0, "moneda": "MXN"}

    mcp_client.call = AsyncMock(side_effect=fake_call)

    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response("get_saldo", {}),
            _mock_final_response(SALDO_A2UI_RESPONSE),
            _mock_function_call_response("get_saldo", {}),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    primer_turno = await orchestrator.handle_message("ana", 1, "¿cuánto tengo?")
    segundo_turno = await orchestrator.handle_message("ana", 1, "¿y ahora?")

    id_turno_1 = primer_turno[0]["createSurface"]["surfaceId"]
    id_turno_2 = segundo_turno[0]["createSurface"]["surfaceId"]
    assert id_turno_1 != id_turno_2
    # Dentro de un mismo turno, los tres mensajes comparten el mismo id.
    assert primer_turno[1]["updateComponents"]["surfaceId"] == id_turno_1
    assert primer_turno[2]["updateDataModel"]["surfaceId"] == id_turno_1


@pytest.mark.asyncio
async def test_handle_message_llama_mcp_con_account_id_inyectado():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], {"saldo": 500.0, "moneda": "MXN"}, None, None])

    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response("get_saldo", {}),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    messages = await orchestrator.handle_message("ana", 1, "¿cuánto tengo?")

    mcp_client.call.assert_any_await("get_saldo", {"account_id": "ana"})
    assert messages[0]["createSurface"]["surfaceId"].startswith("turno-")


@pytest.mark.asyncio
async def test_handle_message_ignora_account_id_que_intente_inyectar_el_llm():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], {"saldo": 500.0, "moneda": "MXN"}, None, None])

    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response("get_saldo", {"account_id": "luis"}),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", 1, "¿cuánto tengo?")

    mcp_client.call.assert_any_await("get_saldo", {"account_id": "ana"})


@pytest.mark.asyncio
async def test_handle_message_simular_flujo_de_caja_reenvia_argumentos():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(
        side_effect=[
            [],
            {
                "alcanza": False,
                "saldo_minimo_proyectado": 500.0,
                "fecha_critica": "2026-10-13",
                "margen": -570.0,
                "apartado_sugerido": {"monto_por_periodo": 142.5, "periodicidad": "semanal", "num_periodos": 4},
            },
            None,
            None,
        ]
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
    await orchestrator.handle_message("ana", 1, "¿me alcanza para el concierto?")

    mcp_client.call.assert_any_await(
        "simular_flujo_de_caja",
        {"account_id": "ana", "fecha_objetivo": "2026-10-13", "monto_objetivo": 8000.0},
    )


@pytest.mark.asyncio
async def test_handle_message_buscar_contacto_reenvia_query():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(
        side_effect=[[], [{"id": 1, "nombre": "José Ramírez", "alias": "Pepe"}], None, None]
    )

    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response("buscar_contacto", {"query": "pepe"}),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", 1, "deposítale a pepe")

    mcp_client.call.assert_any_await("buscar_contacto", {"account_id": "ana", "query": "pepe"})


@pytest.mark.asyncio
async def test_handle_message_respuesta_no_valida_cae_a_bloque_de_error():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[]])
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_final_response("esto no tiene bloque a2ui"),
            _mock_final_response("tampoco esto"),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    messages = await orchestrator.handle_message("ana", 1, "hola")

    assert messages == error_a2ui_block(
        messages[2]["updateDataModel"]["value"]["mensaje"],
        surface_id=messages[0]["createSurface"]["surfaceId"],
    )


@pytest.mark.asyncio
async def test_handle_message_excepcion_en_reintento_de_autocorreccion_cae_a_bloque_de_error():
    # Si la respuesta inicial no trae un bloque A2UI válido, handle_message pide
    # una auto-corrección al modelo; si esa segunda llamada a generate_content
    # explota, tampoco debe propagar la excepción cruda: al ser una excepción
    # inesperada más, activa el mismo fallback a modo offline que cualquier otra
    # falla (en vez de propagarse cruda o cortar el turno sin respuesta).
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[]])
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_final_response("esto no tiene bloque a2ui"),
            RuntimeError("la API de Gemini falló"),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    messages = await orchestrator.handle_message("ana", 1, "hola")

    assert "createSurface" in messages[0]
    valores = next(m for m in messages if "updateDataModel" in m)["updateDataModel"]["value"]
    assert "offline" in str(valores).lower()


@pytest.mark.asyncio
async def test_handle_message_respuesta_sin_id_root_se_autocorrige():
    # El parser real de a2ui (integrity_checker.py) YA valida que exista un
    # componente con id="root" y lanza A2uiIntegrityError si falta — cae en
    # el mismo mecanismo de auto-corrección que cualquier otro JSON A2UI
    # inválido. Esto confirma que ese caso no necesita un chequeo propio: ya
    # está cubierto aguas abajo por la librería.
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], None, None])
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_final_response(SALDO_SIN_ROOT_A2UI_RESPONSE),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    messages = await orchestrator.handle_message("ana", 1, "¿cuál es mi saldo?")

    componentes = next(m for m in messages if "updateComponents" in m)["updateComponents"]["components"]
    assert any(c["id"] == "root" for c in componentes)

    segunda_llamada_contents = genai_client.models.generate_content.call_args_list[1].kwargs["contents"]
    assert any("root" in str(c) for c in segunda_llamada_contents)


@pytest.mark.asyncio
async def test_handle_message_error_esperado_del_mcp_se_devuelve_al_modelo_para_que_reintente():
    # Ej. el usuario pide una fecha_objetivo inválida para simular_flujo_de_caja:
    # el error debe llegar al modelo como function response (para que pida una
    # fecha válida en el siguiente turno de la conversación), no cortar todo
    # el mensaje con un bloque de error genérico.
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(
        side_effect=[[], RuntimeError("fecha_objetivo no puede ser anterior a hoy"), None, None]
    )

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
    messages = await orchestrator.handle_message("ana", 1, "¿me alcanza para algo en 2020?")

    assert genai_client.models.generate_content.call_count == 2
    assert messages[0]["createSurface"]["surfaceId"].startswith("turno-")


@pytest.mark.asyncio
async def test_handle_message_excepcion_no_prevista_cae_a_bloque_de_error():
    # Una excepción no prevista (ej. KeyError) durante el tool loop tampoco debe
    # propagarse cruda: activa el fallback a modo offline igual que cualquier
    # otra falla inesperada (quota, red, etc.).
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], KeyError("algo salió mal de forma inesperada")])

    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[_mock_function_call_response("get_saldo", {})]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    messages = await orchestrator.handle_message("ana", 1, "¿cuánto tengo?")

    assert "createSurface" in messages[0]
    valores = next(m for m in messages if "updateDataModel" in m)["updateDataModel"]["value"]
    assert "offline" in str(valores).lower()


@pytest.mark.asyncio
async def test_handle_message_proponer_transferencia_resuelve_contacto_y_no_ejecuta_nada():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(
        side_effect=[
            [],
            {"id": 1, "nombre": "José Ramírez", "alias": "Pepe", "cuenta_destino": "9988776655", "relacion": "hermano"},
            None,
            None,
        ]
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
    await orchestrator.handle_message("ana", 1, "deposítale 500 a Pepe mi hermano")

    mcp_client.call.assert_any_await("get_contacto", {"account_id": "ana", "contacto_id": 1})
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
    mcp_client.call = AsyncMock(
        side_effect=[[], RuntimeError("Contacto no encontrado para esta cuenta: 999"), None, None]
    )

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
    await orchestrator.handle_message("ana", 1, "deposítale a alguien que no existe")

    assert len(proposals.PROPOSALS) == 0


@pytest.mark.asyncio
async def test_handle_message_proponer_transferencia_monto_no_positivo_no_crea_propuesta():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], None, None])

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
    await orchestrator.handle_message("ana", 1, "transfiere -500")

    llamadas = [c.args[0] for c in mcp_client.call.call_args_list]
    assert "get_contacto" not in llamadas
    assert len(proposals.PROPOSALS) == 0


@pytest.mark.asyncio
async def test_handle_message_proponer_apartado_crea_propuesta_sin_tocar_mcp():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], None, None])

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
    await orchestrator.handle_message("ana", 1, "activa el apartado")

    llamadas = [c.args[0] for c in mcp_client.call.call_args_list]
    assert llamadas == ["obtener_mensajes_conversacion", "agregar_mensaje_conversacion", "agregar_mensaje_conversacion"]
    assert len(proposals.PROPOSALS) == 1
    proposal = next(iter(proposals.PROPOSALS.values()))
    assert proposal.tipo == "apartado"
    assert proposal.payload == {"meta_id": 7, "monto_por_periodo": 142.5, "periodicidad": "semanal"}


@pytest.mark.asyncio
async def test_handle_message_proponer_apartado_monto_no_positivo_no_crea_propuesta():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], None, None])
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
    await orchestrator.handle_message("ana", 1, "activa un apartado de 0")

    assert len(proposals.PROPOSALS) == 0


def test_reparsear_mensaje_modelo_reconstruye_la_tarjeta_a2ui():
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", MagicMock())

    resultado = orchestrator.reparsear_mensaje_modelo(SALDO_A2UI_RESPONSE)

    assert resultado is not None
    assert "createSurface" in resultado[0]


def test_reparsear_mensaje_modelo_asigna_un_surface_id_fresco():
    # Igual que en un turno en vivo: reabrir el historial no debe reusar el
    # surfaceId original (podría chocar con uno ya presente en la sesión).
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", MagicMock())

    resultado = orchestrator.reparsear_mensaje_modelo(SALDO_A2UI_RESPONSE)

    assert resultado[0]["createSurface"]["surfaceId"] != "main"


def test_reparsear_mensaje_modelo_con_texto_invalido_devuelve_none():
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", MagicMock())

    assert orchestrator.reparsear_mensaje_modelo("esto no es un bloque a2ui válido") is None


def test_obtener_resumen_propuesta_devuelve_tipo_y_resumen():
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", MagicMock())
    proposal = proposals.crear_propuesta(
        "ana", "transferencia", {"monto": 500.0}, "Transferir $500.00 a José Ramírez"
    )

    resumen = orchestrator.obtener_resumen_propuesta("ana", proposal.id)

    assert resumen == {"tipo": "transferencia", "resumen": "Transferir $500.00 a José Ramírez"}
    # Es de solo lectura: no debe descartar la propuesta como sí lo hace confirm_action.
    assert proposal.id in proposals.PROPOSALS


def test_obtener_resumen_propuesta_inexistente_devuelve_none():
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", MagicMock())

    assert orchestrator.obtener_resumen_propuesta("ana", "no-existe") is None


def test_obtener_resumen_propuesta_de_otra_cuenta_devuelve_none():
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", MagicMock())
    proposal = proposals.crear_propuesta("ana", "transferencia", {}, "Transferir $500.00")

    assert orchestrator.obtener_resumen_propuesta("luis", proposal.id) is None


def test_generar_propuesta_sugerencia_devuelve_el_texto_del_modelo():
    genai_client = MagicMock()
    genai_client.models.generate_content.return_value = MagicMock(
        text="Considera adelantar este pago para evitar quedarte corto.\n"
    )
    orchestrator = Orchestrator(genai_client, "gemini-test", MagicMock())

    propuesta = orchestrator.generar_propuesta_sugerencia(
        "Pago próximo: Agua", "$320.00 vence el 15 sep 2026."
    )

    assert propuesta == "Considera adelantar este pago para evitar quedarte corto."
    kwargs = genai_client.models.generate_content.call_args.kwargs
    assert "Pago próximo: Agua" in kwargs["contents"][0]
    assert "$320.00 vence el 15 sep 2026." in kwargs["contents"][0]


def test_generar_propuesta_sugerencia_sin_texto_devuelve_cadena_vacia():
    genai_client = MagicMock()
    genai_client.models.generate_content.return_value = MagicMock(text=None)
    orchestrator = Orchestrator(genai_client, "gemini-test", MagicMock())

    assert orchestrator.generar_propuesta_sugerencia("Título", "Descripción") == ""


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
async def test_confirm_action_descarta_propuesta_antes_de_llamar_al_mcp():
    # Cierra la ventana de doble ejecución: la propuesta debe quedar descartada
    # ANTES de que se dispare la llamada al MCP que ejecuta la mutación real, no
    # después (en un finally al final). Lo verificamos observando el estado de
    # PROPOSALS desde dentro del propio side_effect de la llamada al MCP.
    proposal = proposals.crear_propuesta(
        "ana", "apartado", {"meta_id": 7, "monto_por_periodo": 142.5, "periodicidad": "semanal"}, "Apartar $142.50"
    )

    seen_still_present = "not observed"

    async def fake_call(_name, _args):
        nonlocal seen_still_present
        seen_still_present = proposal.id in proposals.PROPOSALS
        return {"ok": True, "apartado": {"id": 1}}

    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=fake_call)
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)

    await orchestrator.confirm_action("ana", proposal.id)

    assert seen_still_present is False
    assert proposal.id not in proposals.PROPOSALS


@pytest.mark.asyncio
async def test_confirm_action_transferencia_revalida_contacto_y_ejecuta():
    # El payload guardado en la propuesta trae una cuenta destino DISTINTA a la que
    # devuelve la revalidación de get_contacto (simula que el contacto cambió su
    # cuenta destino entre proponer y confirmar). Esto prueba que ejecutar_transferencia
    # usa SIEMPRE el valor recién revalidado, nunca el valor obsoleto guardado en la
    # propuesta -- es el comportamiento de seguridad más importante de esta tarea.
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
        {"contacto_id": 1, "destino_cuenta": "OLD_ACCOUNT", "monto": 142.5, "concepto": "Regalo"},
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

    assert messages == error_a2ui_block(
        messages[2]["updateDataModel"]["value"]["mensaje"],
        surface_id=messages[0]["createSurface"]["surfaceId"],
    )
    assert proposal.id not in proposals.PROPOSALS


def test_read_only_tool_declarations_expone_exactamente_las_herramientas_permitidas():
    # Regresión: si alguien agrega 'ejecutar_transferencia', 'crear_apartado',
    # 'get_contacto' o 'autenticar' a esta lista (o la deriva de list_tools()),
    # este test debe fallar de inmediato.
    tools = read_only_tool_declarations()
    names = {fn.name for tool in tools for fn in tool.function_declarations}
    assert names == {
        "get_saldo",
        "get_cuenta",
        "get_resumen_movimientos",
        "get_ingresos_programados",
        "get_gastos_fijos",
        "get_metas",
        "buscar_contacto",
        "simular_flujo_de_caja",
        "calcular_score_salud_financiera",
        "detectar_picos_gasto",
        "proponer_transferencia",
        "proponer_apartado",
        "proponer_contacto",
        "proponer_gasto_fijo",
        "proponer_ingreso_programado",
        "proponer_meta",
    }


@pytest.mark.asyncio
async def test_handle_message_herramienta_no_permitida_no_llama_al_mcp():
    # 'ejecutar_transferencia' nunca debe ser invocable desde /api/chat: solo
    # confirm_action (tras una confirmación explícita del usuario) puede
    # dispararla. _dispatch_tool_call debe negarse y el turno debe completarse
    # igual (sin crash), devolviéndole el error al modelo como function response.
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], None, None])

    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response(
                "ejecutar_transferencia",
                {"origen_id": "ana", "destino_cuenta": "123", "monto": 500.0, "concepto": "x"},
            ),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    messages = await orchestrator.handle_message("ana", 1, "ejecuta la transferencia ya")

    llamadas = [c.args[0] for c in mcp_client.call.call_args_list]
    assert "ejecutar_transferencia" not in llamadas
    assert messages[0]["createSurface"]["surfaceId"].startswith("turno-")


@pytest.mark.asyncio
async def test_handle_message_proponer_transferencia_sin_contacto_id_no_truena():
    # Si Gemini omite un argumento "requerido" (contacto_id), _dispatch_tool_call
    # debe devolver un {"error": ...} recuperable en vez de dejar que un KeyError
    # escape y caiga al bloque de error genérico de handle_message.
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], None, None])

    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_function_call_response(
                "proponer_transferencia", {"monto": 500.0, "concepto": "Renta"}
            ),
            _mock_final_response(SALDO_A2UI_RESPONSE),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    messages = await orchestrator.handle_message("ana", 1, "deposítale 500 a Renta")

    llamadas = [c.args[0] for c in mcp_client.call.call_args_list]
    assert "get_contacto" not in llamadas
    assert len(proposals.PROPOSALS) == 0
    assert messages[0]["createSurface"]["surfaceId"].startswith("turno-")


@pytest.mark.asyncio
async def test_confirm_action_propuesta_inexistente_o_ajena_cae_a_error():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock()
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)

    messages = await orchestrator.confirm_action("ana", "no-existe")

    mcp_client.call.assert_not_called()
    assert messages == error_a2ui_block(
        messages[2]["updateDataModel"]["value"]["mensaje"],
        surface_id=messages[0]["createSurface"]["surfaceId"],
    )


@pytest.mark.asyncio
async def test_handle_message_proponer_contacto_crea_propuesta_sin_tocar_mcp():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], None, None])
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
    await orchestrator.handle_message("ana", 1, "agrega a mi amiga Sofía")

    llamadas = [c.args[0] for c in mcp_client.call.call_args_list]
    assert llamadas == ["obtener_mensajes_conversacion", "agregar_mensaje_conversacion", "agregar_mensaje_conversacion"]
    assert len(proposals.PROPOSALS) == 1
    proposal = next(iter(proposals.PROPOSALS.values()))
    assert proposal.tipo == "contacto"
    assert proposal.payload["nombre"] == "Sofía López"


@pytest.mark.asyncio
async def test_handle_message_proponer_contacto_sin_nombre_no_crea_propuesta():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], None, None])
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
    await orchestrator.handle_message("ana", 1, "agrega un contacto")
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
async def test_confirm_action_contacto_usa_los_valores_editados_del_context():
    # El usuario corrigió el nombre y agregó la cuenta destino en la tarjeta
    # (ver ADR sobre edición en confirmación) antes de tocar "Confirmar" — el
    # dato real ejecutado debe ser el editado, no el que el modelo propuso.
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(return_value={"id": 1, "nombre": "Mamá"})
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    proposal = proposals.crear_propuesta(
        "ana",
        "contacto",
        {"nombre": "Mama", "alias": "Mama", "cuenta_destino": "0000000000", "relacion": "Familia"},
        "Agregar a Mama (Mama) como contacto",
    )
    messages = await orchestrator.confirm_action(
        "ana",
        proposal.id,
        context={"nombre": "Mamá", "cuenta_destino": "1234567890"},
    )
    mcp_client.call.assert_awaited_once_with(
        "crear_contacto",
        {
            "account_id": "ana",
            "nombre": "Mamá",
            "alias": "Mama",
            "cuenta_destino": "1234567890",
            "relacion": "Familia",
        },
    )
    assert "createSurface" in messages[0]


@pytest.mark.asyncio
async def test_confirm_action_contacto_context_no_puede_sobreescribir_account_id():
    # `account_id` nunca es un campo editable: si el context lo trae, se
    # ignora — el candado de proponer/confirmar (ADR 0009) no debe poder
    # abrirse editando un campo que la tarjeta nunca expuso como TextField.
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(return_value={"id": 1})
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    proposal = proposals.crear_propuesta(
        "ana",
        "contacto",
        {"nombre": "Sofía López", "alias": "Sofi", "cuenta_destino": "5566778899", "relacion": "amiga"},
        "Agregar a Sofía López (Sofi) como contacto",
    )
    await orchestrator.confirm_action(
        "ana", proposal.id, context={"account_id": "luis", "nombre": "Sofía López"}
    )
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


@pytest.mark.asyncio
async def test_confirm_action_contacto_context_con_campo_requerido_vacio_no_ejecuta_y_conserva_la_propuesta():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(return_value={"id": 1})
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    proposal = proposals.crear_propuesta(
        "ana",
        "contacto",
        {"nombre": "Sofía López", "alias": "Sofi", "cuenta_destino": "5566778899", "relacion": "amiga"},
        "Agregar a Sofía López (Sofi) como contacto",
    )
    messages = await orchestrator.confirm_action(
        "ana", proposal.id, context={"cuenta_destino": ""}
    )
    mcp_client.call.assert_not_awaited()
    mensajes_texto = [
        m["updateDataModel"]["value"].get("mensaje", "") for m in messages if "updateDataModel" in m
    ]
    assert any("cuenta_destino" in texto for texto in mensajes_texto)
    # La propuesta sigue viva: el usuario puede corregir el campo en la misma
    # tarjeta y confirmar de nuevo sin tener que pedirle al modelo que la
    # rehaga desde cero.
    assert proposal.id in proposals.PROPOSALS


@pytest.mark.asyncio
async def test_confirm_action_gasto_fijo_usa_el_monto_editado_del_context():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(return_value={"id": 1})
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    proposal = proposals.crear_propuesta(
        "ana",
        "gasto_fijo",
        {"concepto": "Internet", "monto": 600.0, "frecuencia": "mensual", "proxima_fecha": "2026-10-05"},
        "Agregar gasto fijo: Internet ($600.00 mensual)",
    )
    await orchestrator.confirm_action("ana", proposal.id, context={"monto": "750.50"})
    mcp_client.call.assert_awaited_once_with(
        "crear_gasto_fijo",
        {
            "account_id": "ana",
            "concepto": "Internet",
            "monto": 750.50,
            "frecuencia": "mensual",
            "proxima_fecha": "2026-10-05",
        },
    )


@pytest.mark.asyncio
async def test_confirm_action_gasto_fijo_context_con_monto_no_numerico_no_ejecuta():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(return_value={"id": 1})
    genai_client = MagicMock()
    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    proposal = proposals.crear_propuesta(
        "ana",
        "gasto_fijo",
        {"concepto": "Internet", "monto": 600.0, "frecuencia": "mensual", "proxima_fecha": "2026-10-05"},
        "Agregar gasto fijo: Internet ($600.00 mensual)",
    )
    await orchestrator.confirm_action("ana", proposal.id, context={"monto": "no-es-un-numero"})
    mcp_client.call.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_message_proponer_gasto_fijo_crea_propuesta_sin_tocar_mcp():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], None, None])
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
    await orchestrator.handle_message("ana", 1, "tengo un gasto fijo de internet de 600 mensual")
    llamadas = [c.args[0] for c in mcp_client.call.call_args_list]
    assert "crear_gasto_fijo" not in llamadas
    proposal = next(iter(proposals.PROPOSALS.values()))
    assert proposal.tipo == "gasto_fijo"


@pytest.mark.asyncio
async def test_handle_message_proponer_gasto_fijo_monto_no_positivo_no_crea_propuesta():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], None, None])
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
    await orchestrator.handle_message("ana", 1, "gasto de 0")
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
    mcp_client.call = AsyncMock(side_effect=[[], None, None])
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
    await orchestrator.handle_message("ana", 1, "voy a recibir un bono anual de 5000")
    llamadas = [c.args[0] for c in mcp_client.call.call_args_list]
    assert "crear_ingreso_programado" not in llamadas
    proposal = next(iter(proposals.PROPOSALS.values()))
    assert proposal.tipo == "ingreso_programado"


@pytest.mark.asyncio
async def test_handle_message_proponer_ingreso_programado_monto_no_positivo_no_crea_propuesta():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], None, None])
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
    await orchestrator.handle_message("ana", 1, "ingreso de 0")
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
    mcp_client.call = AsyncMock(side_effect=[[], None, None])
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
    await orchestrator.handle_message("ana", 1, "quiero ahorrar para un viaje")
    llamadas = [c.args[0] for c in mcp_client.call.call_args_list]
    assert "crear_meta" not in llamadas
    proposal = next(iter(proposals.PROPOSALS.values()))
    assert proposal.tipo == "meta"


@pytest.mark.asyncio
async def test_handle_message_proponer_meta_monto_no_positivo_no_crea_propuesta():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], None, None])
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
    await orchestrator.handle_message("ana", 1, "meta de 0")
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


def test_get_movimientos_ya_no_esta_en_read_only_tools():
    from me_alcanza.backend.orchestrator import _READ_ONLY_TOOLS

    assert "get_movimientos" not in _READ_ONLY_TOOLS
    assert "get_resumen_movimientos" in _READ_ONLY_TOOLS


@pytest.mark.asyncio
async def test_handle_message_get_resumen_movimientos_reenvia_fechas():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(
        side_effect=[[], [{"categoria": "ahorro", "total": -100.0, "count": 2}], None, None]
    )
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
    await orchestrator.handle_message("ana", 1, "¿en qué gasté este mes?")

    mcp_client.call.assert_any_await(
        "get_resumen_movimientos",
        {"account_id": "ana", "fecha_inicio": "2026-09-01", "fecha_fin": "2026-09-30"},
    )


def test_modal_esta_en_allowed_components():
    from me_alcanza.backend.orchestrator import _ALLOWED_COMPONENTS

    assert "Modal" in _ALLOWED_COMPONENTS


def test_system_prompt_instruye_explicabilidad():
    prompt = build_system_prompt()
    assert "Modal" in prompt
    assert "Cómo se calculó" in prompt


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
async def test_handle_message_limita_historial_a_los_ultimos_10_mensajes():
    # El historial completo NO debe reenviarse a Gemini en cada turno: eso
    # multiplica el costo en tokens sin límite a medida que crece la
    # conversación. Solo se reenvían los últimos 10 mensajes de historial
    # (más el mensaje nuevo del usuario).
    historial_largo = [
        {"rol": "user" if i % 2 == 0 else "model", "contenido": f"mensaje {i}"} for i in range(14)
    ]
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(
        side_effect=[
            historial_largo,
            None,  # agregar_mensaje_conversacion (mensaje del usuario)
            None,  # agregar_mensaje_conversacion (respuesta del modelo)
        ]
    )
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(side_effect=[_mock_final_response(SALDO_A2UI_RESPONSE)])

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", 1, "¿cuánto tengo?")

    contents_enviados = genai_client.models.generate_content.call_args.kwargs["contents"]
    # 10 mensajes de historial (los más recientes) + 1 mensaje nuevo = 11.
    assert len(contents_enviados) == 11
    ultimos_esperados = [f"mensaje {i}" for i in range(4, 14)]
    contenidos_historial_enviados = [
        p.text for c in contents_enviados[:-1] for p in c.parts
    ]
    assert contenidos_historial_enviados == ultimos_esperados


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


@pytest.mark.asyncio
async def test_handle_message_provider_fake_no_llama_a_generate_content():
    # provider="fake" debe saltarse Gemini por completo: nunca se llama a
    # generate_content, solo se usa la salida determinista de fake_provider.
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], None, None])
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock()

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client, provider="fake")
    messages = await orchestrator.handle_message("ana", 1, "¿cuál es mi saldo?")

    genai_client.models.generate_content.assert_not_called()
    assert "createSurface" in messages[0]


@pytest.mark.asyncio
async def test_handle_message_provider_fake_excepcion_cae_a_bloque_de_error_generico():
    # Si el provider YA es "fake" y algo dentro del try explota (ej. la carga
    # de historial), no tiene sentido reintentar el fallback offline (ya
    # estamos en modo offline): debe caer directo al bloque de error genérico,
    # nunca a una segunda tarjeta offline.
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=RuntimeError("fallo al cargar historial"))
    genai_client = MagicMock()

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client, provider="fake")
    messages = await orchestrator.handle_message("ana", 1, "hola")

    assert messages == error_a2ui_block(
        messages[2]["updateDataModel"]["value"]["mensaje"],
        surface_id=messages[0]["createSurface"]["surfaceId"],
    )


@pytest.mark.asyncio
async def test_handle_message_fallback_offline_no_persiste_historial():
    # Requisito global: el fallback offline nunca contamina el historial de la
    # conversación -- una respuesta de emergencia no debe guardarse como si
    # fuera un turno real.
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], None, None])
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(side_effect=RuntimeError("429 cuota agotada"))

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    await orchestrator.handle_message("ana", 1, "¿cuál es mi saldo?")

    llamadas = [c.args[0] for c in mcp_client.call.call_args_list]
    assert "agregar_mensaje_conversacion" not in llamadas


@pytest.mark.asyncio
async def test_handle_message_provider_fake_no_persiste_historial():
    # Mismo requisito que el fallback offline: provider="fake" también
    # produce una respuesta de emergencia (boilerplate de fake_provider), no
    # una respuesta real del modelo, así que tampoco debe guardarse en el
    # historial de la conversación -- de lo contrario, al volver a un
    # provider real, Gemini recibiría sus propias afirmaciones fabricadas de
    # estar offline como si fueran contexto legítimo de turnos anteriores.
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], None, None])
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock()

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client, provider="fake")
    await orchestrator.handle_message("ana", 1, "¿cuál es mi saldo?")

    llamadas = [c.args[0] for c in mcp_client.call.call_args_list]
    assert "agregar_mensaje_conversacion" not in llamadas


@pytest.mark.asyncio
async def test_handle_message_fallo_al_persistir_no_descarta_respuesta_exitosa():
    # Regresión del hallazgo crítico: una excepción al persistir el turno
    # (lock de sqlite, conversación borrada, caída del MCP) jamás debe tirar
    # una respuesta ya generada con éxito ni reemplazarla por una tarjeta
    # offline falsa.
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], RuntimeError("persist failed")])
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(side_effect=[_mock_final_response(SALDO_A2UI_RESPONSE)])

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    messages = await orchestrator.handle_message("ana", 1, "¿cuánto tengo?")

    assert "createSurface" in messages[0]
    valores = next(m for m in messages if "updateDataModel" in m)["updateDataModel"]["value"]
    assert "offline" not in str(valores).lower()
    assert valores == {"msg": "Tu saldo es $500.0 MXN"}
