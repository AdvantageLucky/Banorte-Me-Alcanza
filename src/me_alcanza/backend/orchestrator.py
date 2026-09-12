from typing import Any

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.inference_formats.direct_json.format import DirectJsonFormat
from google.genai import types

from . import proposals
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


def _as_function_response_payload(value: Any) -> dict:
    # google.genai.types.FunctionResponse valida que `response` sea un dict:
    # las tools que devuelven list (get_movimientos, buscar_contacto) se
    # envuelven para poder viajar de vuelta al modelo como function response.
    if isinstance(value, dict):
        return value
    return {"result": value}


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

    def _generate_content_config(self) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=self._system_prompt,
            tools=self._tool_declarations(),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

    async def _run_tool_loop(self, account_id: str, contents: list) -> str:
        config = self._generate_content_config()

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
                    types.Part.from_function_response(
                        name=call.name,
                        response=_as_function_response_payload(tool_result),
                    )
                )

        return ""

    async def _dispatch_tool_call(self, account_id: str, call) -> Any:
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

        # Descartar la propuesta ANTES de llamar al MCP: si dos confirmaciones
        # concurrentes de la misma propuesta llegaran a pasar la validación de
        # arriba, solo una debe poder ejecutar la mutación real (transferencia o
        # apartado). Descartar al final (en un finally) dejaría una ventana en la
        # que ambas pasan la validación y ambas ejecutan la acción dos veces.
        proposals.descartar_propuesta(proposal_id)

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

    async def handle_message(self, account_id: str, mensaje: str) -> list[dict]:
        contents = [mensaje]

        # Todo el flujo (tool loop + el reintento de auto-corrección de abajo) vive
        # bajo un único try/except: una excepción en CUALQUIER punto -incluyendo la
        # llamada a generate_content del reintento- debe caer al bloque de error,
        # nunca propagarse cruda fuera de handle_message.
        try:
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
                        return part.a2ui_json

                break
        except Exception as exc:  # noqa: BLE001 - fallback controlado hacia UI de error
            return error_a2ui_block(f"Ocurrió un error al procesar tu solicitud: {exc}")

        return error_a2ui_block("No se pudo generar una respuesta válida. Intenta de nuevo.")
