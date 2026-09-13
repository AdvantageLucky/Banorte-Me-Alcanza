"""Adaptador que expone la misma superficie mínima que `Orchestrator` usa de
`google.genai.Client` (`.models.generate_content(model=, contents=, config=)`
devolviendo algo con `.function_calls`, `.candidates[0].content` y `.text`),
pero por dentro llama a la API de OpenAI (Chat Completions + tool calling).

Por qué un adaptador y no reescribir el orquestador: `orchestrator.py` ya está
fuertemente probado (incluye varias rondas de fixes sobre el tool-loop, la
persistencia de conversación y el fallback offline). Cambiarle el proveedor
por dentro reutiliza `google.genai.types.Content`/`Part` como lo que
realmente son — contenedores de datos sin conexión a red propia, no algo
atado a Gemini — así el tool-loop, `handle_message` y sus ~250 tests
existentes no se tocan. Ver ADR 0022.

Alcance deliberado: solo tool-calling de una vuelta por llamada (igual que
`_run_tool_loop`, que ya maneja el ciclo de rondas por su cuenta) y texto de
salida. No se soporta streaming ni contenido multimodal — el orquestador no
los usa.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from google.genai import types


def _schema_to_json_schema(schema: types.Schema | None) -> dict:
    """Convierte un `types.Schema` de google-genai a un dict de JSON Schema
    plano, el formato que espera `parameters` en un tool de OpenAI. Los tipos
    de ambos SDKs son un subconjunto de JSON Schema, así que esto es solo un
    cambio de forma de objeto, no de semántica."""
    if schema is None:
        return {"type": "object", "properties": {}}

    _TYPE_NAMES = {
        types.Type.OBJECT: "object",
        types.Type.STRING: "string",
        types.Type.NUMBER: "number",
        types.Type.INTEGER: "integer",
        types.Type.BOOLEAN: "boolean",
        types.Type.ARRAY: "array",
    }
    result: dict[str, Any] = {"type": _TYPE_NAMES.get(schema.type, "string")}
    if schema.description:
        result["description"] = schema.description
    if schema.type == types.Type.OBJECT:
        result["properties"] = {
            k: _schema_to_json_schema(v) for k, v in (schema.properties or {}).items()
        }
    if schema.required:
        result["required"] = list(schema.required)
    if schema.items:
        result["items"] = _schema_to_json_schema(schema.items)
    return result


def _tools_to_openai(tools: list[types.Tool] | None) -> list[dict] | None:
    if not tools:
        return None
    result = []
    for tool in tools:
        for declaration in tool.function_declarations or []:
            result.append(
                {
                    "type": "function",
                    "function": {
                        "name": declaration.name,
                        "description": declaration.description or "",
                        "parameters": _schema_to_json_schema(declaration.parameters),
                    },
                }
            )
    return result or None


def _part_text(part: types.Part) -> str:
    return part.text or ""


def _content_to_openai_messages(
    system_instruction: str | None, contents: list
) -> list[dict]:
    """Recorre `contents` en orden y lo traduce a mensajes estilo OpenAI.

    Correlación de tool calls: Gemini no trae un id único por llamada — el
    código existente correlaciona por posición dentro del turno (ver
    `_run_tool_loop`: agrega el content del modelo con N function_call parts,
    y LUEGO, en el mismo orden en que iteró `response.function_calls`, agrega
    N Part de function_response sueltos). Esto importa porque el prompt del
    sistema pide explícitamente llamar la MISMA tool varias veces en un turno
    (ej. `proponer_transferencia` una vez por contacto ambiguo) — no se puede
    correlacionar por nombre. Por eso aquí se asignan ids sintéticos por
    posición (una cola FIFO) en vez de usar el nombre de la tool como id.
    """
    messages: list[dict] = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})

    pending_call_ids: list[str] = []
    call_counter = 0

    for item in contents:
        if isinstance(item, str):
            messages.append({"role": "user", "content": item})
            continue

        if isinstance(item, types.Part):
            if item.function_response is not None:
                call_id = pending_call_ids.pop(0) if pending_call_ids else f"call_{call_counter}"
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(item.function_response.response),
                    }
                )
            elif item.text is not None:
                messages.append({"role": "user", "content": item.text})
            continue

        if isinstance(item, types.Content):
            parts = item.parts or []
            function_call_parts = [p for p in parts if p.function_call is not None]
            if function_call_parts:
                tool_calls = []
                # Se descarta cualquier id pendiente de una tanda anterior en vez de
                # dejarlo disponible: una tanda sin resolver no debería poder ser
                # "recogida" por las function_response de esta tanda nueva.
                pending_call_ids = []
                for fc_part in function_call_parts:
                    call_id = f"call_{call_counter}"
                    call_counter += 1
                    pending_call_ids.append(call_id)
                    fc = fc_part.function_call
                    tool_calls.append(
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": fc.name,
                                "arguments": json.dumps(dict(fc.args or {})),
                            },
                        }
                    )
                messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
            else:
                role = "assistant" if item.role == "model" else "user"
                text = "".join(_part_text(p) for p in parts)
                messages.append({"role": role, "content": text})
            continue

    return messages


@dataclass
class _FunctionCall:
    name: str
    args: dict


@dataclass
class _Response:
    text: str | None
    function_calls: list[_FunctionCall] = field(default_factory=list)
    candidates: list = field(default_factory=list)


@dataclass
class _Candidate:
    content: Any


class _Models:
    def __init__(self, client, default_model: str | None = None):
        self._client = client
        self._default_model = default_model

    def generate_content(self, *, model: str, contents: list, config: types.GenerateContentConfig | None = None):
        system_instruction = config.system_instruction if config else None
        tools = config.tools if config else None
        messages = _content_to_openai_messages(system_instruction, contents)
        oa_tools = _tools_to_openai(tools)

        kwargs: dict[str, Any] = {"model": model or self._default_model, "messages": messages}
        if oa_tools:
            kwargs["tools"] = oa_tools
        response = self._client.chat.completions.create(**kwargs)
        choice = response.choices[0].message

        if choice.tool_calls:
            function_calls = [
                _FunctionCall(name=tc.function.name, args=json.loads(tc.function.arguments or "{}"))
                for tc in choice.tool_calls
            ]
            model_content = types.Content(
                role="model",
                parts=[
                    types.Part.from_function_call(name=fc.name, args=fc.args)
                    for fc in function_calls
                ],
            )
            return _Response(
                text=None,
                function_calls=function_calls,
                candidates=[_Candidate(content=model_content)],
            )

        return _Response(text=choice.content or "", function_calls=[], candidates=[])


class OpenAICompatClient:
    """Se usa donde el orquestador espera un `google.genai.Client`. Solo
    implementa `.models.generate_content(...)`, que es todo lo que
    `orchestrator.py` llama."""

    def __init__(self, openai_client, model: str | None = None):
        self.models = _Models(openai_client, default_model=model)
