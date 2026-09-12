import logging
import uuid
from typing import Any

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.inference_formats.direct_json.format import DirectJsonFormat
from google.genai import types

from . import fake_provider, proposals
from .mcp_client import BankMcpClient

_logger = logging.getLogger(__name__)

_VERSION = "0.9"
_ALLOWED_COMPONENTS = ["Card", "Column", "Row", "Text", "Button", "List", "Divider", "Modal"]
MAX_TOOL_CALL_ROUNDS = 5
# Cuántos mensajes de historial (no turnos) se reenvían a Gemini como
# contexto: últimos 10 mensajes ≈ últimos 5 pares usuario/modelo.
_MAX_HISTORIAL_MENSAJES = 10

_READ_ONLY_TOOLS = {
    "get_saldo",
    "get_cuenta",
    "get_resumen_movimientos",
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


_SURFACE_MESSAGE_KEYS = ("createSurface", "updateComponents", "updateDataModel")


def _new_surface_id() -> str:
    # Cada turno de la conversación recibe su propia superficie: así se apila
    # como una transcripción de chat en vez de sobrescribir la misma tarjeta.
    return f"turno-{uuid.uuid4().hex[:8]}"


def _rewrite_surface_id(a2ui_json: list[dict], surface_id: str) -> list[dict]:
    # El LLM decide el contenido del bloque A2UI, pero nunca el surfaceId: se
    # fuerza aquí a un id nuevo por turno, sin depender de que el modelo lo
    # elija (ni de que sea consistente consigo mismo dentro de su propia
    # respuesta) — evita repetir el bug de compatibilidad de SDK que ya
    # tuvimos cuando confiábamos en que el modelo reutilizara un id fijo.
    rewritten = []
    for message in a2ui_json:
        message = dict(message)
        for key in _SURFACE_MESSAGE_KEYS:
            if key in message:
                payload = dict(message[key])
                payload["surfaceId"] = surface_id
                message[key] = payload
        rewritten.append(message)
    return rewritten


def error_a2ui_block(mensaje: str, surface_id: str | None = None) -> list[dict]:
    surface_id = surface_id or _new_surface_id()
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


def _confirmation_a2ui_block(mensaje: str, surface_id: str | None = None) -> list[dict]:
    surface_id = surface_id or _new_surface_id()
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
                    name="get_resumen_movimientos",
                    description=(
                        "Obtiene el total y conteo de movimientos de la cuenta del usuario actual, "
                        "agrupados por categoría, dentro de un rango de fechas. Úsala para responder "
                        "preguntas sobre patrones de gasto (ej. '¿en qué gasté este mes?'); nunca "
                        "pidas el detalle de movimientos individuales."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "fecha_inicio": types.Schema(
                                type=types.Type.STRING, description="Formato YYYY-MM-DD."
                            ),
                            "fecha_fin": types.Schema(
                                type=types.Type.STRING, description="Formato YYYY-MM-DD."
                            ),
                        },
                        required=["fecha_inicio", "fecha_fin"],
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
                        "resultado, llama a esta herramienta UNA VEZ POR CADA candidato en el mismo "
                        "turno, en vez de esperar a que el usuario elija en otro mensaje). "
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
                types.FunctionDeclaration(
                    name="proponer_contacto",
                    description=(
                        "Propone agregar un contacto/beneficiario nuevo a la lista del usuario. "
                        "NO lo crea: solo genera una propuesta que el usuario debe confirmar "
                        "explícitamente en la UI."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "nombre": types.Schema(type=types.Type.STRING),
                            "alias": types.Schema(type=types.Type.STRING),
                            "cuenta_destino": types.Schema(type=types.Type.STRING),
                            "relacion": types.Schema(type=types.Type.STRING),
                        },
                        required=["nombre", "alias", "cuenta_destino", "relacion"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="proponer_gasto_fijo",
                    description=(
                        "Propone agregar un gasto fijo recurrente nuevo (ej. renta, colegiatura) a "
                        "la cuenta del usuario. NO lo crea: solo genera una propuesta que el usuario "
                        "debe confirmar explícitamente en la UI."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "concepto": types.Schema(type=types.Type.STRING),
                            "monto": types.Schema(type=types.Type.NUMBER),
                            "frecuencia": types.Schema(type=types.Type.STRING),
                            "proxima_fecha": types.Schema(
                                type=types.Type.STRING, description="Formato YYYY-MM-DD."
                            ),
                        },
                        required=["concepto", "monto", "frecuencia", "proxima_fecha"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="proponer_ingreso_programado",
                    description=(
                        "Propone agregar un ingreso recurrente nuevo (ej. nómina, renta cobrada) a "
                        "la cuenta del usuario. NO lo crea: solo genera una propuesta que el usuario "
                        "debe confirmar explícitamente en la UI."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "descripcion": types.Schema(type=types.Type.STRING),
                            "monto": types.Schema(type=types.Type.NUMBER),
                            "frecuencia": types.Schema(type=types.Type.STRING),
                            "proxima_fecha": types.Schema(
                                type=types.Type.STRING, description="Formato YYYY-MM-DD."
                            ),
                        },
                        required=["descripcion", "monto", "frecuencia", "proxima_fecha"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="proponer_meta",
                    description=(
                        "Propone crear una meta de ahorro nueva. NO la crea: solo genera una "
                        "propuesta que el usuario debe confirmar explícitamente en la UI."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "descripcion": types.Schema(type=types.Type.STRING),
                            "monto_objetivo": types.Schema(type=types.Type.NUMBER),
                            "fecha_objetivo": types.Schema(
                                type=types.Type.STRING, description="Formato YYYY-MM-DD."
                            ),
                        },
                        required=["descripcion", "monto_objetivo", "fecha_objetivo"],
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
            "'buscar_contacto' con el nombre que mencione el usuario. Si el resultado tiene un solo "
            "contacto, usa 'proponer_transferencia' con su id y muestra una tarjeta de confirmación "
            "con un botón cuya acción sea el evento 'confirmar_accion' con context={'proposalId': "
            "'<el id que te devolvió esa llamada>'}. Si el resultado tiene más de un contacto "
            "(nombre ambiguo), NO esperes a que el usuario responda en otro mensaje para elegir "
            "(la conversación no conserva memoria entre turnos): en cambio, en el MISMO turno llama "
            "a 'proponer_transferencia' una vez POR CADA contacto candidato (cada llamada es "
            "independiente y devuelve su propio proposalId) y muestra una tarjeta de confirmación "
            "POR CADA candidato, cada una con su botón 'confirmar_accion' llevando el "
            "context={'proposalId': '<el id devuelto por esa llamada específica>'} correspondiente "
            "a ESE candidato; el usuario desambigua simplemente confirmando la tarjeta correcta. "
            "Nunca afirmes que una transferencia o un apartado ya se realizó: solo se ejecutan "
            "cuando el usuario confirma explícitamente. Nunca inventes saldos, movimientos, "
            "ingresos, gastos, metas o contactos: siempre usa el resultado real de las herramientas. "
            "El surfaceId que uses no importa: el sistema le asigna uno nuevo a cada turno "
            "automáticamente, así que usa cualquier id consistente dentro de tu propia respuesta "
            "(el mismo en createSurface, updateComponents y updateDataModel de este turno). "
            "Para agregar datos nuevos que el usuario mencione en la conversación (un "
            "contacto/beneficiario nuevo, un gasto fijo nuevo, un ingreso programado nuevo, o una "
            "meta de ahorro nueva), usa 'proponer_contacto', 'proponer_gasto_fijo', "
            "'proponer_ingreso_programado' o 'proponer_meta' según corresponda, y muestra una "
            "tarjeta de confirmación con el mismo patrón de 'confirmar_accion' + proposalId que ya "
            "usas para transferencias y apartados. Nunca afirmes que un contacto, gasto fijo, "
            "ingreso programado o meta ya se guardó: solo se crean cuando el usuario confirma "
            "explícitamente. Estas herramientas son solo para CREAR: editar o borrar un contacto/"
            "gasto fijo/ingreso programado/meta existente no se hace por chat, dile al usuario que "
            "lo haga desde la pantalla correspondiente. "
            "Para preguntas sobre patrones de gasto (ej. '¿en qué gasté este mes?', '¿cuánto gasté en "
            "transferencias?'), usa 'get_resumen_movimientos' calculando tú mismo el rango de fechas a "
            "partir de hoy (ej. 'este mes' = del día 1 del mes actual a hoy); nunca pidas ni inventes "
            "el detalle de movimientos individuales."
        ),
        ui_description=(
            "Usa SIEMPRE jerarquía visual, nunca texto plano sin estructura: "
            "1) Todo Text lleva un 'variant' explícito según su rol — 'h3' para el título de la "
            "tarjeta (ej. 'Saldo disponible', 'Confirmar transferencia'), 'h1' o 'h2' para el dato "
            "numérico principal (el monto o saldo destacado), 'body' para texto descriptivo normal, "
            "y 'caption' para etiquetas secundarias o aclaraciones pequeñas. Nunca dejes 'variant' "
            "sin especificar para un título o un monto destacado. "
            "2) Para pares etiqueta-valor (ej. 'Concepto: Renta', 'Fecha: 15 oct'), usa un Row con "
            "justify='spaceBetween' conteniendo la etiqueta (variant='caption' o 'body') y el valor "
            "(variant='body'), nunca los concatenes en un solo Text. "
            "3) Separa secciones distintas dentro de una misma tarjeta (ej. el resumen de un dato y "
            "la acción de confirmación debajo) con un Divider entre ellas. "
            "4) En cada Button, usa variant='primary' para la única acción principal/de confirmación "
            "de la tarjeta (ej. el botón que dispara 'confirmar_accion'), y variant='borderless' o "
            "'default' para acciones secundarias si las hay. Nunca dejes el variant del botón "
            "principal sin especificar. "
            "5) Envuelve el contenido de cada Card en un Column con algo de estructura (título, "
            "luego el contenido, nunca un solo Text suelto como único hijo) — una tarjeta con un "
            "solo dato sin título ni jerarquía se ve incompleta y debe evitarse. "
            "6) Para cualquier tarjeta que muestre un número calculado o derivado (un saldo "
            "proyectado, el margen de 'simular_flujo_de_caja', el desglose de una transferencia con "
            "puntos, etc.), agrega un componente Modal como hijo directo de la Column de la tarjeta. "
            "El Modal se renderiza a sí mismo como el elemento que el usuario toca: su 'trigger' debe "
            "ser el id de un Text (variant='caption') con el texto '¿Cómo se calculó?', y su 'content' "
            "el id de una Column mostrando los montos y fechas concretos que entraron a ese cálculo. "
            "No agregues el trigger ni el content como hijos separados de la tarjeta — el Modal ya los "
            "renderiza. Nunca agregues este componente para datos que ya son un valor directo de una "
            "herramienta (ej. el saldo actual tal cual, sin proyección) — solo para números que el LLM "
            "o una herramienta derivaron a partir de otros datos."
        ),
        allowed_components=_ALLOWED_COMPONENTS,
        include_schema=True,
    )


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

    def _tool_declarations(self) -> list[types.Tool]:
        return read_only_tool_declarations()

    def _generate_content_config(self) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=self._system_prompt,
            tools=self._tool_declarations(),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
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
            if call.name == "get_resumen_movimientos":
                call_args = call.args or {}
                fecha_inicio = call_args.get("fecha_inicio")
                fecha_fin = call_args.get("fecha_fin")
                if fecha_inicio is None:
                    return {"error": "Falta el argumento requerido: fecha_inicio"}
                if fecha_fin is None:
                    return {"error": "Falta el argumento requerido: fecha_fin"}
                args["fecha_inicio"] = fecha_inicio
                args["fecha_fin"] = fecha_fin
            elif call.name == "buscar_contacto":
                query = (call.args or {}).get("query")
                if query is None:
                    return {"error": "Falta el argumento requerido: query"}
                args["query"] = query
            elif call.name == "simular_flujo_de_caja":
                call_args = call.args or {}
                fecha_objetivo = call_args.get("fecha_objetivo")
                monto_objetivo = call_args.get("monto_objetivo")
                if fecha_objetivo is None:
                    return {"error": "Falta el argumento requerido: fecha_objetivo"}
                if monto_objetivo is None:
                    return {"error": "Falta el argumento requerido: monto_objetivo"}
                args["fecha_objetivo"] = fecha_objetivo
                args["monto_objetivo"] = float(monto_objetivo)
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

        if call.name == "proponer_contacto":
            return self._proponer_contacto(account_id, call.args)

        if call.name == "proponer_gasto_fijo":
            return self._proponer_gasto_fijo(account_id, call.args)

        if call.name == "proponer_ingreso_programado":
            return self._proponer_ingreso_programado(account_id, call.args)

        if call.name == "proponer_meta":
            return self._proponer_meta(account_id, call.args)

        return {"error": f"Herramienta no permitida: {call.name}"}

    async def _proponer_transferencia(self, account_id: str, args: dict) -> dict:
        args = args or {}
        monto = args.get("monto")
        if monto is None:
            return {"error": "Falta el argumento requerido: monto"}
        contacto_id = args.get("contacto_id")
        if contacto_id is None:
            return {"error": "Falta el argumento requerido: contacto_id"}
        concepto = args.get("concepto")
        if concepto is None:
            return {"error": "Falta el argumento requerido: concepto"}

        monto = float(monto)
        if monto <= 0:
            return {"error": "El monto debe ser mayor a cero"}

        contacto_id = int(contacto_id)
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
                "concepto": concepto,
            },
            resumen=f"Transferir ${monto:.2f} a {contacto['nombre']}",
        )
        return {"proposalId": proposal.id, "resumen": proposal.resumen}

    def _proponer_apartado(self, account_id: str, args: dict) -> dict:
        args = args or {}
        meta_id = args.get("meta_id")
        if meta_id is None:
            return {"error": "Falta el argumento requerido: meta_id"}
        monto_por_periodo = args.get("monto_por_periodo")
        if monto_por_periodo is None:
            return {"error": "Falta el argumento requerido: monto_por_periodo"}
        periodicidad = args.get("periodicidad")
        if periodicidad is None:
            return {"error": "Falta el argumento requerido: periodicidad"}

        monto_por_periodo = float(monto_por_periodo)
        if monto_por_periodo <= 0:
            return {"error": "monto_por_periodo debe ser mayor a cero"}

        proposal = proposals.crear_propuesta(
            account_id=account_id,
            tipo="apartado",
            payload={
                "meta_id": int(meta_id),
                "monto_por_periodo": monto_por_periodo,
                "periodicidad": periodicidad,
            },
            resumen=f"Apartar ${monto_por_periodo:.2f} {periodicidad} hacia tu meta",
        )
        return {"proposalId": proposal.id, "resumen": proposal.resumen}

    def _proponer_contacto(self, account_id: str, args: dict) -> dict:
        args = args or {}
        nombre = args.get("nombre")
        alias = args.get("alias")
        cuenta_destino = args.get("cuenta_destino")
        relacion = args.get("relacion")
        if not nombre:
            return {"error": "Falta el argumento requerido: nombre"}
        if not alias:
            return {"error": "Falta el argumento requerido: alias"}
        if not cuenta_destino:
            return {"error": "Falta el argumento requerido: cuenta_destino"}
        if not relacion:
            return {"error": "Falta el argumento requerido: relacion"}

        proposal = proposals.crear_propuesta(
            account_id=account_id,
            tipo="contacto",
            payload={
                "nombre": nombre,
                "alias": alias,
                "cuenta_destino": cuenta_destino,
                "relacion": relacion,
            },
            resumen=f"Agregar a {nombre} ({alias}) como contacto",
        )
        return {"proposalId": proposal.id, "resumen": proposal.resumen}

    def _proponer_gasto_fijo(self, account_id: str, args: dict) -> dict:
        args = args or {}
        concepto = args.get("concepto")
        monto = args.get("monto")
        frecuencia = args.get("frecuencia")
        proxima_fecha = args.get("proxima_fecha")
        if not concepto:
            return {"error": "Falta el argumento requerido: concepto"}
        if monto is None:
            return {"error": "Falta el argumento requerido: monto"}
        if not frecuencia:
            return {"error": "Falta el argumento requerido: frecuencia"}
        if not proxima_fecha:
            return {"error": "Falta el argumento requerido: proxima_fecha"}

        monto = float(monto)
        if monto <= 0:
            return {"error": "El monto debe ser mayor a cero"}

        proposal = proposals.crear_propuesta(
            account_id=account_id,
            tipo="gasto_fijo",
            payload={
                "concepto": concepto,
                "monto": monto,
                "frecuencia": frecuencia,
                "proxima_fecha": proxima_fecha,
            },
            resumen=f"Agregar gasto fijo: {concepto} (${monto:.2f} {frecuencia})",
        )
        return {"proposalId": proposal.id, "resumen": proposal.resumen}

    def _proponer_ingreso_programado(self, account_id: str, args: dict) -> dict:
        args = args or {}
        descripcion = args.get("descripcion")
        monto = args.get("monto")
        frecuencia = args.get("frecuencia")
        proxima_fecha = args.get("proxima_fecha")
        if not descripcion:
            return {"error": "Falta el argumento requerido: descripcion"}
        if monto is None:
            return {"error": "Falta el argumento requerido: monto"}
        if not frecuencia:
            return {"error": "Falta el argumento requerido: frecuencia"}
        if not proxima_fecha:
            return {"error": "Falta el argumento requerido: proxima_fecha"}

        monto = float(monto)
        if monto <= 0:
            return {"error": "El monto debe ser mayor a cero"}

        proposal = proposals.crear_propuesta(
            account_id=account_id,
            tipo="ingreso_programado",
            payload={
                "descripcion": descripcion,
                "monto": monto,
                "frecuencia": frecuencia,
                "proxima_fecha": proxima_fecha,
            },
            resumen=f"Agregar ingreso programado: {descripcion} (${monto:.2f} {frecuencia})",
        )
        return {"proposalId": proposal.id, "resumen": proposal.resumen}

    def _proponer_meta(self, account_id: str, args: dict) -> dict:
        args = args or {}
        descripcion = args.get("descripcion")
        monto_objetivo = args.get("monto_objetivo")
        fecha_objetivo = args.get("fecha_objetivo")
        if not descripcion:
            return {"error": "Falta el argumento requerido: descripcion"}
        if monto_objetivo is None:
            return {"error": "Falta el argumento requerido: monto_objetivo"}
        if not fecha_objetivo:
            return {"error": "Falta el argumento requerido: fecha_objetivo"}

        monto_objetivo = float(monto_objetivo)
        if monto_objetivo <= 0:
            return {"error": "El monto_objetivo debe ser mayor a cero"}

        proposal = proposals.crear_propuesta(
            account_id=account_id,
            tipo="meta",
            payload={
                "descripcion": descripcion,
                "monto_objetivo": monto_objetivo,
                "fecha_objetivo": fecha_objetivo,
            },
            resumen=f"Crear meta: {descripcion} (${monto_objetivo:.2f})",
        )
        return {"proposalId": proposal.id, "resumen": proposal.resumen}

    def obtener_resumen_propuesta(self, account_id: str, proposal_id: str) -> dict | None:
        # El frontend usa esto para mostrar un modal de confirmación nativo
        # (no generado por A2UI) justo antes de ejecutar la acción: el
        # 'resumen' que devolvemos aquí lo construyó este mismo backend con
        # f-strings sobre datos ya validados (ver _proponer_transferencia y
        # compañía), nunca texto que el LLM haya escrito — así el usuario
        # siempre confirma contra el dato real, sin depender de que el modelo
        # lo haya transcrito bien en la tarjeta.
        proposal = proposals.obtener_propuesta_valida(proposal_id, account_id)
        if proposal is None:
            return None
        return {"tipo": proposal.tipo, "resumen": proposal.resumen}

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
                return _confirmation_a2ui_block(
                    "Apartado de ahorro activado correctamente."
                )

            if proposal.tipo == "transferencia":
                try:
                    contacto = await self._mcp.call(
                        "get_contacto",
                        {
                            "account_id": account_id,
                            "contacto_id": proposal.payload["contacto_id"],
                        },
                    )
                except RuntimeError:
                    return error_a2ui_block(
                        "El contacto de esta propuesta ya no existe."
                    )

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

            if proposal.tipo == "contacto":
                await self._mcp.call(
                    "crear_contacto",
                    {
                        "account_id": account_id,
                        "nombre": proposal.payload["nombre"],
                        "alias": proposal.payload["alias"],
                        "cuenta_destino": proposal.payload["cuenta_destino"],
                        "relacion": proposal.payload["relacion"],
                    },
                )
                return _confirmation_a2ui_block(
                    f"Contacto {proposal.payload['nombre']} agregado correctamente."
                )

            if proposal.tipo == "gasto_fijo":
                await self._mcp.call(
                    "crear_gasto_fijo",
                    {
                        "account_id": account_id,
                        "concepto": proposal.payload["concepto"],
                        "monto": proposal.payload["monto"],
                        "frecuencia": proposal.payload["frecuencia"],
                        "proxima_fecha": proposal.payload["proxima_fecha"],
                    },
                )
                return _confirmation_a2ui_block(
                    f"Gasto fijo '{proposal.payload['concepto']}' agregado correctamente."
                )

            if proposal.tipo == "ingreso_programado":
                await self._mcp.call(
                    "crear_ingreso_programado",
                    {
                        "account_id": account_id,
                        "descripcion": proposal.payload["descripcion"],
                        "monto": proposal.payload["monto"],
                        "frecuencia": proposal.payload["frecuencia"],
                        "proxima_fecha": proposal.payload["proxima_fecha"],
                    },
                )
                return _confirmation_a2ui_block(
                    f"Ingreso programado '{proposal.payload['descripcion']}' agregado correctamente."
                )

            if proposal.tipo == "meta":
                await self._mcp.call(
                    "crear_meta",
                    {
                        "account_id": account_id,
                        "descripcion": proposal.payload["descripcion"],
                        "monto_objetivo": proposal.payload["monto_objetivo"],
                        "fecha_objetivo": proposal.payload["fecha_objetivo"],
                    },
                )
                return _confirmation_a2ui_block(
                    f"Meta '{proposal.payload['descripcion']}' creada correctamente."
                )

            return error_a2ui_block(f"Tipo de propuesta desconocido: {proposal.tipo}")
        except Exception:  # noqa: BLE001 - fallback controlado hacia UI de error
            # Nunca se interpola el texto crudo de la excepción en el mensaje
            # que ve el usuario: puede traer payloads de proveedores externos
            # (ej. el cuerpo de error de la API de Gemini en un 429 de cuota,
            # que incluye límites, links y detalles internos). El detalle real
            # queda solo en el log del servidor.
            _logger.exception("confirm_action falló de forma inesperada")
            return error_a2ui_block(
                "No se pudo completar la acción. Intenta de nuevo en unos momentos."
            )

    async def handle_message(self, account_id: str, conversacion_id: int, mensaje: str) -> list[dict]:
        # Todo el flujo (carga de historial, tool loop y el reintento de
        # auto-corrección de abajo) vive bajo un único try/except: una excepción
        # en CUALQUIER punto -incluyendo la carga de historial y la llamada a
        # generate_content del reintento- debe caer al bloque de error, nunca
        # propagarse cruda fuera de handle_message.
        try:
            historial = await self._mcp.call(
                "obtener_mensajes_conversacion", {"account_id": account_id, "conversacion_id": conversacion_id}
            )
            # Solo se reenvían los últimos N turnos: reenviar el historial
            # completo en cada llamada a generate_content (hasta
            # MAX_TOOL_CALL_ROUNDS veces por turno) multiplica el costo en
            # tokens sin límite a medida que crece la conversación, arriesgando
            # la misma cuota que el modo offline existe para proteger.
            contents = [
                types.Content(role=m["rol"], parts=[types.Part.from_text(text=m["contenido"])])
                for m in historial[-_MAX_HISTORIAL_MENSAJES:]
            ]
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=mensaje)]))

            # es_respuesta_offline rastrea si final_text vino de
            # fake_provider (boilerplate de modo offline) en vez de una
            # respuesta real del modelo: una respuesta offline nunca debe
            # persistirse en el historial de la conversación, para no
            # contaminar turnos futuros con afirmaciones fabricadas de que
            # "el servicio no está disponible".
            es_respuesta_offline = False
            if self._provider == "fake":
                final_text = fake_provider.generar_respuesta_offline(mensaje)
                es_respuesta_offline = True
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
                        # La persistencia del turno se protege en su propio
                        # try/except, separado del try externo que activa el
                        # fallback offline: una falla al guardar (lock de sqlite,
                        # conversación borrada a mitad del turno, caída del
                        # transporte MCP) nunca debe tirar una respuesta ya
                        # generada con éxito ni disfrazarla de una respuesta
                        # offline falsa. Solo se loguea.
                        # Nunca se persiste una respuesta offline/fake: es
                        # boilerplate de emergencia, no una respuesta real del
                        # modelo, y guardarla contaminaría el contexto de
                        # turnos futuros si más adelante se vuelve a un
                        # provider real.
                        if not es_respuesta_offline:
                            try:
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
                            except Exception:  # noqa: BLE001 - no persistir no debe tirar una respuesta ya exitosa
                                _logger.exception(
                                    "no se pudo persistir el turno de conversación, "
                                    "la respuesta ya se generó con éxito"
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
