from unittest.mock import MagicMock

import pytest
from google.genai import types

from me_alcanza.backend.anthropic_compat_client import AnthropicCompatClient
from me_alcanza.backend.orchestrator import Orchestrator, read_only_tool_declarations


def _block(*, type_, **kwargs):
    block = MagicMock()
    block.type = type_
    for k, v in kwargs.items():
        setattr(block, k, v)
    return block


def _mock_anthropic_response(*, text: str | None = None, tool_uses: list[dict] | None = None):
    """tool_uses: lista de {"id": str, "name": str, "input": dict}."""
    blocks = []
    if text is not None:
        blocks.append(_block(type_="text", text=text))
    for tu in tool_uses or []:
        blocks.append(_block(type_="tool_use", id=tu["id"], name=tu["name"], input=tu["input"]))
    response = MagicMock()
    response.content = blocks
    return response


def _config(tools=None, system_instruction="eres un asistente"):
    return types.GenerateContentConfig(system_instruction=system_instruction, tools=tools)


def test_generate_content_respuesta_de_texto_sin_tool_calls():
    anthropic_client = MagicMock()
    anthropic_client.messages.create.return_value = _mock_anthropic_response(text="hola, ¿en qué te ayudo?")

    client = AnthropicCompatClient(anthropic_client, model="claude-opus-5")
    response = client.models.generate_content(model="claude-opus-5", contents=["hola"], config=_config())

    assert response.function_calls == []
    assert response.text == "hola, ¿en qué te ayudo?"


def test_generate_content_envia_system_prompt_y_mensaje_de_usuario():
    anthropic_client = MagicMock()
    anthropic_client.messages.create.return_value = _mock_anthropic_response(text="ok")

    client = AnthropicCompatClient(anthropic_client, model="claude-opus-5")
    contents = [types.Content(role="user", parts=[types.Part.from_text(text="¿cuál es mi saldo?")])]
    client.models.generate_content(
        model="claude-opus-5", contents=contents, config=_config(system_instruction="Eres el asistente de un banco.")
    )

    kwargs = anthropic_client.messages.create.call_args.kwargs
    assert kwargs["system"] == "Eres el asistente de un banco."
    assert kwargs["messages"][0] == {"role": "user", "content": "¿cuál es mi saldo?"}


def test_generate_content_una_sola_tool_call_se_traduce_correctamente():
    anthropic_client = MagicMock()
    anthropic_client.messages.create.return_value = _mock_anthropic_response(
        tool_uses=[{"id": "toolu_real_1", "name": "get_saldo", "input": {}}]
    )

    client = AnthropicCompatClient(anthropic_client, model="claude-opus-5")
    response = client.models.generate_content(model="claude-opus-5", contents=["hola"], config=_config())

    assert response.text is None
    assert len(response.function_calls) == 1
    assert response.function_calls[0].name == "get_saldo"
    assert response.function_calls[0].args == {}
    model_content = response.candidates[0].content
    assert isinstance(model_content, types.Content)
    assert model_content.role == "model"
    assert model_content.parts[0].function_call.name == "get_saldo"


def test_multiples_tool_calls_de_la_misma_tool_se_correlacionan_por_posicion():
    # Mismo escenario que en el adaptador de OpenAI: proponer_transferencia
    # se llama una vez por cada contacto candidato cuando el nombre es
    # ambiguo. Además de correlacionar por posición (no por nombre), Anthropic
    # exige que cada tool_result.tool_use_id coincida con un tool_use.id
    # presente ANTES en la misma request — se verifica también eso.
    anthropic_client = MagicMock()
    anthropic_client.messages.create.return_value = _mock_anthropic_response(
        tool_uses=[
            {"id": "ignorado-1", "name": "proponer_transferencia", "input": {"contacto_id": 1}},
            {"id": "ignorado-2", "name": "proponer_transferencia", "input": {"contacto_id": 2}},
        ]
    )

    client = AnthropicCompatClient(anthropic_client, model="claude-opus-5")
    response = client.models.generate_content(model="claude-opus-5", contents=["hola"], config=_config())

    assert [fc.args["contacto_id"] for fc in response.function_calls] == [1, 2]

    contents = ["hola", response.candidates[0].content]
    contents.append(types.Part.from_function_response(name="proponer_transferencia", response={"proposalId": "p1"}))
    contents.append(types.Part.from_function_response(name="proponer_transferencia", response={"proposalId": "p2"}))

    anthropic_client.messages.create.return_value = _mock_anthropic_response(text="listo")
    client.models.generate_content(model="claude-opus-5", contents=contents, config=_config())

    segunda_llamada = anthropic_client.messages.create.call_args.kwargs["messages"]
    assistant_msg = next(m for m in segunda_llamada if m["role"] == "assistant")
    tool_result_msg = next(m for m in segunda_llamada if m["role"] == "user" and isinstance(m["content"], list))

    ids_asignados = [block["id"] for block in assistant_msg["content"]]
    assert len(set(ids_asignados)) == 2

    tool_use_ids_en_resultados = [block["tool_use_id"] for block in tool_result_msg["content"]]
    assert tool_use_ids_en_resultados == ids_asignados
    assert tool_result_msg["content"][0]["content"] == '{"proposalId": "p1"}'
    assert tool_result_msg["content"][1]["content"] == '{"proposalId": "p2"}'


def test_tools_reales_del_orquestador_se_convierten_sin_error():
    from me_alcanza.backend.anthropic_compat_client import _tools_to_anthropic

    tools = _tools_to_anthropic(read_only_tool_declarations())
    assert tools is not None
    nombres = {t["name"] for t in tools}
    assert "get_resumen_movimientos" in nombres
    resumen_tool = next(t for t in tools if t["name"] == "get_resumen_movimientos")
    params = resumen_tool["input_schema"]
    assert params["type"] == "object"
    assert set(params["required"]) == {"fecha_inicio", "fecha_fin"}


@pytest.mark.asyncio
async def test_orchestrator_completo_con_anthropic_compat_client_de_extremo_a_extremo():
    from unittest.mock import AsyncMock

    from me_alcanza.backend import proposals

    proposals.PROPOSALS.clear()

    anthropic_client = MagicMock()
    anthropic_client.messages.create.side_effect = [
        _mock_anthropic_response(tool_uses=[{"id": "toolu_ignorado", "name": "get_saldo", "input": {}}]),
        _mock_anthropic_response(
            text=(
                "Aquí está tu saldo:\n<a2ui-json>\n"
                '[{"version": "v0.9", "createSurface": {"surfaceId": "main", '
                '"catalogId": "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"}}, '
                '{"version": "v0.9", "updateComponents": {"surfaceId": "main", "components": ['
                '{"id": "root", "component": "Card", "child": "txt"}, '
                '{"id": "txt", "component": "Text", "text": {"path": "/msg"}}]}}, '
                '{"version": "v0.9", "updateDataModel": {"surfaceId": "main", "path": "/", '
                '"value": {"msg": "Tu saldo es $500.0 MXN"}}}]\n</a2ui-json>\n'
            )
        ),
    ]

    mcp_client = MagicMock()
    mcp_client.call = AsyncMock(side_effect=[[], {"saldo": 500.0}, None, None])

    client = AnthropicCompatClient(anthropic_client, model="claude-opus-5")
    orchestrator = Orchestrator(client, "claude-opus-5", mcp_client, provider="anthropic")

    messages = await orchestrator.handle_message("ana", 1, "¿cuál es mi saldo?")

    assert any("createSurface" in m for m in messages)
    valores = next(m for m in messages if "updateDataModel" in m)["updateDataModel"]["value"]
    assert valores == {"msg": "Tu saldo es $500.0 MXN"}

    segunda_llamada = anthropic_client.messages.create.call_args_list[1].kwargs["messages"]
    assistant_msg = next(m for m in segunda_llamada if m["role"] == "assistant")
    tool_result_msg = next(m for m in segunda_llamada if m["role"] == "user" and isinstance(m["content"], list))
    assert tool_result_msg["content"][0]["tool_use_id"] == assistant_msg["content"][0]["id"]
    assert tool_result_msg["content"][0]["content"] == '{"saldo": 500.0}'

    assert mcp_client.call.await_args_list[1].args[0] == "get_saldo"
