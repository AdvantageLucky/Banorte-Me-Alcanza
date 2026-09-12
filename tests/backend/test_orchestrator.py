from unittest.mock import AsyncMock, MagicMock

import pytest
from google.genai import types

from me_alcanza.backend import proposals
from me_alcanza.backend.orchestrator import Orchestrator, error_a2ui_block


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
    messages = await orchestrator.handle_message("ana", "mis últimos movimientos")

    mcp_client.call.assert_awaited_once_with("get_movimientos", {"account_id": "ana", "limit": 3})
    # El resultado de get_movimientos es una list; esto prueba que el round-trip
    # completo (incluyendo Part.from_function_response con ese resultado) termina
    # en el bloque A2UI real y no cae silenciosamente a error_a2ui_block.
    assert messages[0]["createSurface"]["surfaceId"] == "main"


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
