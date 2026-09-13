"""Adaptador que expone la misma superficie mínima que `Orchestrator` usa de
`google.genai.Client` (`.models.generate_content(model=, contents=, config=)`
devolviendo algo con `.function_calls`, `.candidates[0].content` y `.text`),
pero por dentro llama a la API de Anthropic (Messages API + tool use).

Mismo motivo que `openai_compat_client.py` (ver su docstring y ADR 0022):
reutilizar el tool-loop y los ~250 tests de `orchestrator.py` sin tocarlos.
Este es el tercer proveedor (además de Gemini y OpenAI) — ver ADR 0023.

Correlación de tool calls: a diferencia de OpenAI, Anthropic SÍ exige que
cada bloque `tool_result.tool_use_id` coincida EXACTAMENTE con el `id` de un
bloque `tool_use` anterior en la MISMA request. Pero `contents` (la lista
genérica de `google.genai.types.Content`/`Part` que usa el orquestador) no
tiene dónde guardar ese id real de Anthropic — `Part.from_function_call` no
tiene ese campo. La solución es la misma que ya usa el adaptador de OpenAI:
nunca depender del id real que devolvió el proveedor la vez anterior, sino
regenerar ids sintéticos consistentes DENTRO DE CADA traducción de `contents`
a mensajes de Anthropic (mismo orden posicional para el tool_use y su
tool_result correspondiente). Anthropic solo exige consistencia dentro de una
misma request, no que el id sea el mismo que generó en una llamada anterior.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from google.genai import types

from .openai_compat_client import _schema_to_json_schema


def _tools_to_anthropic(tools: list[types.Tool] | None) -> list[dict] | None:
    if not tools:
        return None
    result = []
    for tool in tools:
        for declaration in tool.function_declarations or []:
            result.append(
                {
                    "name": declaration.name,
                    "description": declaration.description or "",
                    "input_schema": _schema_to_json_schema(declaration.parameters),
                }
            )
    return result or None


def _part_text(part: types.Part) -> str:
    return part.text or ""


def _content_to_anthropic_messages(contents: list) -> list[dict]:
    """Recorre `contents` en orden y lo traduce a mensajes estilo Anthropic.

    Los `Part` de function_response consecutivos se agrupan en UN solo
    mensaje `user` con varios bloques `tool_result` (Anthropic los exige así,
    a diferencia de OpenAI que usa un mensaje `tool` por llamada) — se van
    acumulando en `pending_tool_results` y se vacían apenas aparece cualquier
    otra cosa (o al final).
    """
    messages: list[dict] = []
    pending_call_ids: list[str] = []
    pending_tool_results: list[dict] = []
    call_counter = 0

    def flush_tool_results():
        nonlocal pending_tool_results
        if pending_tool_results:
            messages.append({"role": "user", "content": pending_tool_results})
            pending_tool_results = []

    for item in contents:
        if isinstance(item, str):
            flush_tool_results()
            messages.append({"role": "user", "content": item})
            continue

        if isinstance(item, types.Part):
            if item.function_response is not None:
                call_id = pending_call_ids.pop(0) if pending_call_ids else f"toolu_{call_counter}"
                pending_tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call_id,
                        "content": json.dumps(item.function_response.response),
                    }
                )
            elif item.text is not None:
                flush_tool_results()
                messages.append({"role": "user", "content": item.text})
            continue

        if isinstance(item, types.Content):
            flush_tool_results()
            parts = item.parts or []
            function_call_parts = [p for p in parts if p.function_call is not None]
            if function_call_parts:
                # Igual que el adaptador de OpenAI: se descarta cualquier id
                # pendiente de una tanda anterior sin resolver.
                pending_call_ids = []
                content_blocks = []
                for fc_part in function_call_parts:
                    call_id = f"toolu_{call_counter}"
                    call_counter += 1
                    pending_call_ids.append(call_id)
                    fc = fc_part.function_call
                    content_blocks.append(
                        {"type": "tool_use", "id": call_id, "name": fc.name, "input": dict(fc.args or {})}
                    )
                messages.append({"role": "assistant", "content": content_blocks})
            else:
                role = "assistant" if item.role == "model" else "user"
                text = "".join(_part_text(p) for p in parts)
                messages.append({"role": role, "content": text})
            continue

    flush_tool_results()
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
        messages = _content_to_anthropic_messages(contents)
        anthropic_tools = _tools_to_anthropic(tools)

        kwargs: dict[str, Any] = {
            "model": model or self._default_model,
            "max_tokens": 8192,
            "messages": messages,
        }
        if system_instruction:
            kwargs["system"] = system_instruction
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        response = self._client.messages.create(**kwargs)
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        if tool_use_blocks:
            function_calls = [_FunctionCall(name=b.name, args=dict(b.input or {})) for b in tool_use_blocks]
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

        text = "".join(b.text for b in response.content if b.type == "text")
        return _Response(text=text, function_calls=[], candidates=[])


class AnthropicCompatClient:
    """Se usa donde el orquestador espera un `google.genai.Client`. Solo
    implementa `.models.generate_content(...)`, que es todo lo que
    `orchestrator.py` llama."""

    def __init__(self, anthropic_client, model: str | None = None):
        self.models = _Models(anthropic_client, default_model=model)
