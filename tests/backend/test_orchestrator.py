from unittest.mock import AsyncMock, MagicMock

import pytest
from google.genai import types

from me_alcanza.backend import proposals
from me_alcanza.backend.orchestrator import (
    Orchestrator,
    _new_surface_id,
    _rewrite_surface_id,
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


@pytest.mark.asyncio
async def test_handle_message_cada_turno_tiene_su_propia_superficie_unica():
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(return_value={"saldo": 500.0, "moneda": "MXN"})

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
    primer_turno = await orchestrator.handle_message("ana", "¿cuánto tengo?")
    segundo_turno = await orchestrator.handle_message("ana", "¿y ahora?")

    id_turno_1 = primer_turno[0]["createSurface"]["surfaceId"]
    id_turno_2 = segundo_turno[0]["createSurface"]["surfaceId"]
    assert id_turno_1 != id_turno_2
    # Dentro de un mismo turno, los tres mensajes comparten el mismo id.
    assert primer_turno[1]["updateComponents"]["surfaceId"] == id_turno_1
    assert primer_turno[2]["updateDataModel"]["surfaceId"] == id_turno_1


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
    assert messages[0]["createSurface"]["surfaceId"].startswith("turno-")


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
    messages = await orchestrator.handle_message("ana", "mis últimos movimientos")

    mcp_client.call.assert_awaited_once_with("get_movimientos", {"account_id": "ana", "limit": 3})
    # El resultado de get_movimientos es una list; esto prueba que el round-trip
    # completo (incluyendo Part.from_function_response con ese resultado) termina
    # en el bloque A2UI real y no cae silenciosamente a error_a2ui_block.
    assert messages[0]["createSurface"]["surfaceId"].startswith("turno-")


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

    assert messages == error_a2ui_block(
        messages[2]["updateDataModel"]["value"]["mensaje"],
        surface_id=messages[0]["createSurface"]["surfaceId"],
    )


@pytest.mark.asyncio
async def test_handle_message_excepcion_en_reintento_de_autocorreccion_cae_a_bloque_de_error():
    # Si la respuesta inicial no trae un bloque A2UI válido, handle_message pide
    # una auto-corrección al modelo; si esa segunda llamada a generate_content
    # explota, tampoco debe propagar la excepción cruda: debe caer al bloque de
    # error igual que cualquier otra falla inesperada.
    mcp_client = MagicMock()
    genai_client = MagicMock()
    genai_client.models.generate_content = MagicMock(
        side_effect=[
            _mock_final_response("esto no tiene bloque a2ui"),
            RuntimeError("la API de Gemini falló"),
        ]
    )

    orchestrator = Orchestrator(genai_client, "gemini-test", mcp_client)
    messages = await orchestrator.handle_message("ana", "hola")

    assert messages == error_a2ui_block(
        messages[2]["updateDataModel"]["value"]["mensaje"],
        surface_id=messages[0]["createSurface"]["surfaceId"],
    )


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
    assert messages[0]["createSurface"]["surfaceId"].startswith("turno-")


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

    assert messages == error_a2ui_block(
        messages[2]["updateDataModel"]["value"]["mensaje"],
        surface_id=messages[0]["createSurface"]["surfaceId"],
    )


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
        "get_movimientos",
        "get_ingresos_programados",
        "get_gastos_fijos",
        "get_metas",
        "buscar_contacto",
        "simular_flujo_de_caja",
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
    mcp_client.call = AsyncMock()

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
    messages = await orchestrator.handle_message("ana", "ejecuta la transferencia ya")

    mcp_client.call.assert_not_called()
    assert messages[0]["createSurface"]["surfaceId"].startswith("turno-")


@pytest.mark.asyncio
async def test_handle_message_proponer_transferencia_sin_contacto_id_no_truena():
    # Si Gemini omite un argumento "requerido" (contacto_id), _dispatch_tool_call
    # debe devolver un {"error": ...} recuperable en vez de dejar que un KeyError
    # escape y caiga al bloque de error genérico de handle_message.
    mcp_client = MagicMock()
    mcp_client.call = AsyncMock()

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
    messages = await orchestrator.handle_message("ana", "deposítale 500 a Renta")

    mcp_client.call.assert_not_called()
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
