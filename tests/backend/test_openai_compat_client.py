import json
from unittest.mock import MagicMock

import pytest
from google.genai import types

from me_alcanza.backend.openai_compat_client import OpenAICompatClient
from me_alcanza.backend.orchestrator import Orchestrator, read_only_tool_declarations


def _mock_openai_response(*, content: str | None = None, tool_calls: list[dict] | None = None):
    """tool_calls: lista de {"id": str, "name": str, "arguments": dict}."""
    message = MagicMock()
    message.content = content
    if tool_calls:
        mocked_calls = []
        for tc in tool_calls:
            call = MagicMock()
            call.id = tc["id"]
            call.function.name = tc["name"]
            call.function.arguments = json.dumps(tc["arguments"])
            mocked_calls.append(call)
        message.tool_calls = mocked_calls
    else:
        message.tool_calls = None
    response = MagicMock()
    response.choices = [MagicMock(message=message)]
    return response


def _config(tools=None, system_instruction="eres un asistente"):
    return types.GenerateContentConfig(system_instruction=system_instruction, tools=tools)


def test_generate_content_respuesta_de_texto_sin_tool_calls():
    openai_client = MagicMock()
    openai_client.chat.completions.create.return_value = _mock_openai_response(content="hola, ¿en qué te ayudo?")

    client = OpenAICompatClient(openai_client, model="gpt-4o-mini")
    response = client.models.generate_content(model="gpt-4o-mini", contents=["hola"], config=_config())

    assert response.function_calls == []
    assert response.text == "hola, ¿en qué te ayudo?"


def test_generate_content_envia_system_prompt_y_mensaje_de_usuario():
    openai_client = MagicMock()
    openai_client.chat.completions.create.return_value = _mock_openai_response(content="ok")

    client = OpenAICompatClient(openai_client, model="gpt-4o-mini")
    contents = [types.Content(role="user", parts=[types.Part.from_text(text="¿cuál es mi saldo?")])]
    client.models.generate_content(model="gpt-4o-mini", contents=contents, config=_config(system_instruction="Eres el asistente de un banco."))

    kwargs = openai_client.chat.completions.create.call_args.kwargs
    assert kwargs["messages"][0] == {"role": "system", "content": "Eres el asistente de un banco."}
    assert kwargs["messages"][1] == {"role": "user", "content": "¿cuál es mi saldo?"}


def test_generate_content_una_sola_tool_call_se_traduce_correctamente():
    openai_client = MagicMock()
    openai_client.chat.completions.create.return_value = _mock_openai_response(
        tool_calls=[{"id": "abc123", "name": "get_saldo", "arguments": {}}]
    )

    client = OpenAICompatClient(openai_client, model="gpt-4o-mini")
    response = client.models.generate_content(model="gpt-4o-mini", contents=["hola"], config=_config())

    assert response.text is None
    assert len(response.function_calls) == 1
    assert response.function_calls[0].name == "get_saldo"
    assert response.function_calls[0].args == {}
    # El "content" del modelo debe ser reutilizable por el tool-loop existente
    # (se agrega tal cual a `contents` para la siguiente ronda).
    model_content = response.candidates[0].content
    assert isinstance(model_content, types.Content)
    assert model_content.role == "model"
    assert model_content.parts[0].function_call.name == "get_saldo"


def test_multiples_tool_calls_de_la_misma_tool_se_correlacionan_por_posicion_no_por_nombre():
    # Escenario real del prompt del sistema: proponer_transferencia se llama
    # una vez por cada contacto candidato cuando el nombre es ambiguo — dos
    # llamadas a LA MISMA tool en un solo turno. Si se correlacionara por
    # nombre en vez de por posición, ambas respuestas apuntarían al mismo id.
    openai_client = MagicMock()
    openai_client.chat.completions.create.return_value = _mock_openai_response(
        tool_calls=[
            {"id": "ignorado-1", "name": "proponer_transferencia", "arguments": {"contacto_id": 1}},
            {"id": "ignorado-2", "name": "proponer_transferencia", "arguments": {"contacto_id": 2}},
        ]
    )

    client = OpenAICompatClient(openai_client, model="gpt-4o-mini")
    response = client.models.generate_content(model="gpt-4o-mini", contents=["hola"], config=_config())

    assert [fc.args["contacto_id"] for fc in response.function_calls] == [1, 2]

    # Simula lo que hace _run_tool_loop: agrega el content del modelo, y
    # luego un Part.from_function_response por cada llamada, EN EL MISMO
    # ORDEN en que iteró response.function_calls.
    contents = ["hola", response.candidates[0].content]
    contents.append(types.Part.from_function_response(name="proponer_transferencia", response={"proposalId": "p1"}))
    contents.append(types.Part.from_function_response(name="proponer_transferencia", response={"proposalId": "p2"}))

    openai_client.chat.completions.create.return_value = _mock_openai_response(content="listo")
    client.models.generate_content(model="gpt-4o-mini", contents=contents, config=_config())

    segunda_llamada = openai_client.chat.completions.create.call_args.kwargs["messages"]
    assistant_msg = next(m for m in segunda_llamada if m.get("role") == "assistant" and m.get("tool_calls"))
    tool_msgs = [m for m in segunda_llamada if m.get("role") == "tool"]

    ids_asignados = [tc["id"] for tc in assistant_msg["tool_calls"]]
    assert len(set(ids_asignados)) == 2  # ids únicos, no ambos "proponer_transferencia"
    assert [m["tool_call_id"] for m in tool_msgs] == ids_asignados  # mismo orden
    assert json.loads(tool_msgs[0]["content"]) == {"proposalId": "p1"}
    assert json.loads(tool_msgs[1]["content"]) == {"proposalId": "p2"}


def test_tools_reales_del_orquestador_se_convierten_sin_error():
    # read_only_tool_declarations() incluye schemas anidados (ej.
    # get_resumen_movimientos con fecha_inicio/fecha_fin requeridos) — confirma
    # que la conversión real (no un ejemplo simplificado) no truena y produce
    # el formato de tool que espera la API de OpenAI.
    from me_alcanza.backend.openai_compat_client import _tools_to_openai

    oa_tools = _tools_to_openai(read_only_tool_declarations())
    assert oa_tools is not None
    nombres = {t["function"]["name"] for t in oa_tools}
    assert "get_resumen_movimientos" in nombres
    resumen_tool = next(t for t in oa_tools if t["function"]["name"] == "get_resumen_movimientos")
    assert resumen_tool["type"] == "function"
    params = resumen_tool["function"]["parameters"]
    assert params["type"] == "object"
    assert set(params["required"]) == {"fecha_inicio", "fecha_fin"}


@pytest.mark.asyncio
async def test_orchestrator_completo_con_openai_compat_client_de_extremo_a_extremo():
    # Prueba que Orchestrator, sin ningún cambio, funciona igual de bien con
    # OpenAICompatClient que con un google.genai.Client real — el punto
    # central del adaptador. A diferencia de una respuesta de texto directa,
    # esto hace pasar la conversación por _run_tool_loop de VERDAD (dos
    # rondas: una tool call real, luego el texto final), en vez de simular el
    # comportamiento del tool-loop a mano como hacía la versión anterior de
    # este test — lo que probaba una copia del invariante, no el invariante.
    from unittest.mock import AsyncMock

    from me_alcanza.backend import proposals

    proposals.PROPOSALS.clear()

    openai_client = MagicMock()
    openai_client.chat.completions.create.side_effect = [
        _mock_openai_response(tool_calls=[{"id": "ignorado", "name": "get_saldo", "arguments": {}}]),
        _mock_openai_response(
            content=(
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
    # Orden real de mcp.call en handle_message: historial vacío, luego la
    # tool call de get_saldo dentro de _run_tool_loop, luego los 2 persist
    # calls (agregar_mensaje_conversacion) al final del turno.
    mcp_client.call = AsyncMock(side_effect=[[], {"saldo": 500.0}, None, None])

    client = OpenAICompatClient(openai_client, model="gpt-4o-mini")
    orchestrator = Orchestrator(client, "gpt-4o-mini", mcp_client, provider="openai")

    messages = await orchestrator.handle_message("ana", 1, "¿cuál es mi saldo?")

    assert any("createSurface" in m for m in messages)
    valores = next(m for m in messages if "updateDataModel" in m)["updateDataModel"]["value"]
    assert valores == {"msg": "Tu saldo es $500.0 MXN"}

    # El invariante central del adaptador: la segunda llamada a la API debe
    # llevar el tool_call_id real generado en la primera, correlacionado por
    # posición, no un id inventado sin relación con la respuesta anterior.
    segunda_llamada = openai_client.chat.completions.create.call_args_list[1].kwargs["messages"]
    assistant_msg = next(m for m in segunda_llamada if m.get("role") == "assistant" and m.get("tool_calls"))
    tool_msg = next(m for m in segunda_llamada if m.get("role") == "tool")
    assert tool_msg["tool_call_id"] == assistant_msg["tool_calls"][0]["id"]
    assert json.loads(tool_msg["content"]) == {"saldo": 500.0}

    assert mcp_client.call.await_args_list[1].args[0] == "get_saldo"
