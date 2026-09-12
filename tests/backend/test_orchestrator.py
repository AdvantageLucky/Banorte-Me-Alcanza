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
