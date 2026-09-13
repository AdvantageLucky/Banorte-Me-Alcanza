import json
import logging
import uuid
from typing import Any

from a2ui.inference_formats.direct_json.format import DirectJsonFormat
from a2ui.schema.constants import A2UI_CLOSE_TAG, A2UI_OPEN_TAG
from google.genai import types

from . import a2ui_custom_catalog, fake_provider, proposals
from .mcp_client import BankMcpClient

_logger = logging.getLogger(__name__)

_VERSION = "0.9"
_ALLOWED_COMPONENTS = [
    "Card",
    "Column",
    "Row",
    "Text",
    "Button",
    "List",
    "Divider",
    "Modal",
    "Tabs",
    "TextField",
    "CheckBox",
    "ChoicePicker",
    "Slider",
    "DateTimeInput",
    "StatCard",
    "BarChart",
    "PlanDePago",
    "LineChart",
    "ApartadoPlanner",
    "DonutChart",
    "BudgetAllocator",
]
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
    "calcular_score_salud_financiera",
    "detectar_picos_gasto",
}


def _catalog_id() -> str:
    return a2ui_custom_catalog.CUSTOM_CATALOG_ID


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
    #
    # Por la misma razón se fuerza aquí el catalogId de createSurface: el
    # JSON Schema que ve el modelo no restringe ese campo a un valor fijo
    # (es un string libre), así que a veces alucina el catalogId del
    # catálogo básico genérico de la especificación (el que conoce de su
    # entrenamiento) en vez del propio del equipo. El frontend solo registra
    # nuestro catálogo, así que un catalogId ajeno hace que el
    # MessageProcessor truene con "Catalog not found" al procesar un mensaje
    # que sí llegó bien por HTTP — visible para el usuario como "No se pudo
    # enviar el mensaje", con la respuesta completa (pero inútil) en el
    # network tab.
    rewritten = []
    for message in a2ui_json:
        message = dict(message)
        for key in _SURFACE_MESSAGE_KEYS:
            if key in message:
                payload = dict(message[key])
                payload["surfaceId"] = surface_id
                if key == "createSurface":
                    payload["catalogId"] = _catalog_id()
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


def _a2ui_block_to_raw_text(block: list[dict]) -> str:
    """Serializa un bloque A2UI ya armado (ej. `_confirmation_a2ui_block`) al
    mismo formato de texto crudo que produce el LLM, para poder persistirlo
    con `agregar_mensaje_conversacion` y que `reparsear_mensaje_modelo` lo
    reconstruya igual que cualquier otro turno del historial."""
    return f"{A2UI_OPEN_TAG}\n{json.dumps(block)}\n{A2UI_CLOSE_TAG}"


# Campos que el usuario puede corregir en la tarjeta de confirmación antes de
# aceptarla (ver `Orchestrator.confirm_action`) — nunca incluye `account_id`
# ni identificadores de referencia (meta_id, contacto_id): esos no vienen de
# un campo de texto editable, y aceptar un override ahí sería el mismo hueco
# de seguridad que el patrón proponer/confirmar (ADR 0009) existe para evitar.
_CAMPOS_EDITABLES_AL_CONFIRMAR: dict[str, tuple[str, ...]] = {
    # El único campo que ApartadoPlanner/BudgetAllocator ajustan con su
    # slider antes de confirmar — meta_id y periodicidad no son editables en
    # esa tarjeta (ninguna la enlaza a un path del data model).
    "apartado": ("monto_por_periodo",),
    "contacto": ("nombre", "alias", "cuenta_destino", "relacion"),
    "gasto_fijo": ("concepto", "monto", "frecuencia", "proxima_fecha"),
    "ingreso_programado": ("descripcion", "monto", "frecuencia", "proxima_fecha"),
    "meta": ("descripcion", "monto_objetivo", "fecha_objetivo"),
}


def _validar_datos_creacion(tipo: str, payload: dict) -> str | None:
    """Valida un payload de creación (contacto/gasto_fijo/ingreso_programado/
    meta) con la MISMA regla tanto cuando el modelo lo propone por primera vez
    como cuando el usuario lo edita en la tarjeta de confirmación — así una
    edición nunca puede colar un dato que `proponer_*` ya habría rechazado.
    Coacciona los campos de monto a `float` in-place cuando son válidos, para
    que el llamador guarde/reenvíe el mismo tipo sin importar si el valor
    vino de la tool del modelo (ya numérico) o de un TextField editado a mano
    (string)."""
    if tipo == "apartado":
        if payload.get("meta_id") is None:
            return "Falta el argumento requerido: meta_id"
        if payload.get("monto_por_periodo") is None:
            return "Falta el argumento requerido: monto_por_periodo"
        if not payload.get("periodicidad"):
            return "Falta el argumento requerido: periodicidad"
        try:
            monto_por_periodo = float(payload["monto_por_periodo"])
        except (TypeError, ValueError):
            return "monto_por_periodo debe ser un número válido"
        if monto_por_periodo <= 0:
            return "monto_por_periodo debe ser mayor a cero"
        payload["monto_por_periodo"] = monto_por_periodo
        return None

    if tipo == "contacto":
        for campo in ("nombre", "alias", "cuenta_destino", "relacion"):
            if not payload.get(campo):
                return f"Falta el argumento requerido: {campo}"
        return None

    if tipo in ("gasto_fijo", "ingreso_programado"):
        campo_nombre = "concepto" if tipo == "gasto_fijo" else "descripcion"
        if not payload.get(campo_nombre):
            return f"Falta el argumento requerido: {campo_nombre}"
        if payload.get("monto") is None:
            return "Falta el argumento requerido: monto"
        if not payload.get("frecuencia"):
            return "Falta el argumento requerido: frecuencia"
        if not payload.get("proxima_fecha"):
            return "Falta el argumento requerido: proxima_fecha"
        try:
            monto = float(payload["monto"])
        except (TypeError, ValueError):
            return "El monto debe ser un número válido"
        if monto <= 0:
            return "El monto debe ser mayor a cero"
        payload["monto"] = monto
        return None

    if tipo == "meta":
        if not payload.get("descripcion"):
            return "Falta el argumento requerido: descripcion"
        if payload.get("monto_objetivo") is None:
            return "Falta el argumento requerido: monto_objetivo"
        if not payload.get("fecha_objetivo"):
            return "Falta el argumento requerido: fecha_objetivo"
        try:
            monto_objetivo = float(payload["monto_objetivo"])
        except (TypeError, ValueError):
            return "El monto_objetivo debe ser un número válido"
        if monto_objetivo <= 0:
            return "El monto_objetivo debe ser mayor a cero"
        payload["monto_objetivo"] = monto_objetivo
        return None

    return None


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
                    name="calcular_score_salud_financiera",
                    description=(
                        "Calcula un score 0-100 de salud financiera de la cuenta del usuario "
                        "actual, con categoria ('Saludable'/'Atención'/'Riesgo') y los factores "
                        "que lo explican. Úsala cuando el usuario pregunte por su salud "
                        "financiera en general (ej. '¿cómo ando de finanzas?', '¿voy bien?') o "
                        "cuando quieras cerrar una respuesta mostrando el panorama completo."
                    ),
                    parameters=types.Schema(type=types.Type.OBJECT, properties={}),
                ),
                types.FunctionDeclaration(
                    name="detectar_picos_gasto",
                    description=(
                        "Detecta categorías cuyo gasto en un rango de fechas excede su propio "
                        "promedio histórico (de la misma cuenta, en periodos previos de igual "
                        "duración) por 40% o más — devuelve categoria, total_actual, "
                        "promedio_historico, factor y severidad ('media'|'alta'). Úsala junto "
                        "con 'get_resumen_movimientos' para el MISMO rango de fechas cuando "
                        "vayas a mostrar un BarChart de gastos por categoría, para marcar con "
                        "tone las categorías que dispararon un pico real."
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
        version=_VERSION, catalogs=[a2ui_custom_catalog.get_config(_VERSION)]
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
            "Si el resultado de 'buscar_contacto' está vacío (ningún candidato, ej. el usuario "
            "menciona a alguien que no está en su lista de contactos), NO llames a "
            "'proponer_transferencia' ni inventes un contacto: muestra una tarjeta simple "
            "explicando que no encontraste a esa persona en sus contactos y sugiriendo agregarla "
            "primero con 'proponer_contacto' si de verdad quiere transferirle. "
            "Nunca afirmes que una transferencia o un apartado ya se realizó: solo se ejecutan "
            "cuando el usuario confirma explícitamente. Nunca inventes saldos, movimientos, "
            "ingresos, gastos, metas o contactos: siempre usa el resultado real de las herramientas. "
            "Si el usuario pide repetir o rehacer una acción mencionada antes en esta misma "
            "conversación (ej. 'vuelve a hacer ese depósito', 'repite la transferencia anterior'), "
            "el historial que ves incluye el JSON A2UI completo que generaste en ese turno: "
            "extrae de ahí el contacto/monto/concepto que usaste y vuelve a llamar a "
            "'buscar_contacto' + 'proponer_transferencia' (o la tool que corresponda) desde cero. "
            "Nunca reutilices un proposalId de una tarjeta anterior: cada propuesta es de un solo "
            "uso y expira sola, así que un proposalId viejo ya no sirve aunque lo veas en tu "
            "propio historial. "
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
            "el detalle de movimientos individuales. "
            "Para preguntas sobre salud financiera general, usa 'calcular_score_salud_financiera' y "
            "muestra su score, categoría y factores tal cual los devuelve la herramienta; nunca "
            "calcules o inventes tú mismo ese score."
        ),
        ui_description=(
            "REGLA OBLIGATORIA antes que cualquier otra: el componente de nivel superior de "
            "cada tarjeta (el que va como hijo directo del surface, normalmente un Card) SIEMPRE "
            "debe tener exactamente \"id\": \"root\" dentro de 'updateComponents'. Si usas "
            "cualquier otro id para el componente raíz (o lo omites), tu respuesta se rechaza y "
            "se te pide corregirla, desperdiciando un turno completo. Todos los demás ids pueden "
            "ser lo que quieras, pero el raíz de cada tarjeta que generes es siempre \"root\". "
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
            "4.1) OBLIGATORIO: toda tarjeta con un botón 'confirmar_accion' debe traer TAMBIÉN un "
            "botón secundario (variant='borderless', texto 'Cancelar' o similar) con "
            "action.event.name='rechazar_accion' y el MISMO context={'proposalId': "
            "'<el mismo id>'} — el usuario necesita poder decir que no de forma explícita, no solo "
            "ignorar la tarjeta. "
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
            "o una herramienta derivaron a partir de otros datos. "
            "7) Además de Card/Column/Row/Text/Button/List/Divider/Modal, tienes disponibles "
            "TextField, CheckBox, ChoicePicker, Slider, DateTimeInput y Tabs. Úsalos solo cuando "
            "aporten valor real, nunca como decoración: "
            "DateTimeInput para que el usuario elija una fecha (ej. cuándo programar un ingreso, "
            "la fecha límite de una meta) — pon enableDate=true; "
            "Slider para que el usuario ajuste un monto o porcentaje dentro de un rango conocido "
            "(ej. cuánto apartar de una meta, qué porcentaje de un ingreso destinar a algo); "
            "ChoicePicker para elegir entre opciones ya conocidas (ej. categoría de un gasto fijo, "
            "cuenta de destino) en vez de pedirlo como texto libre; "
            "CheckBox para una decisión sí/no dentro de un formulario más grande (ej. 'marcar como "
            "recurrente'); "
            "TextField solo para texto libre que ninguna otra herramienta puede resolver (ej. el "
            "nombre de un contacto nuevo o el concepto de un gasto); "
            "Tabs para agrupar contenido relacionado pero independiente dentro de la misma tarjeta "
            "(ej. 'Resumen' y 'Detalle'), nunca para pasos de un mismo flujo. "
            "Todo componente de entrada (TextField, CheckBox, ChoicePicker, Slider, DateTimeInput) "
            "SIEMPRE debe enlazar su 'value' a un path del data model (ej. {\"path\": \"/monto\"}), "
            "nunca a un literal fijo, y ESE MISMO path debe inicializarse en updateDataModel con un "
            "valor por default. El botón que confirma SIEMPRE dispara el evento 'confirmar_accion' "
            "(nunca inventes otro nombre de evento — el backend solo reconoce ese), y su "
            "'action.event.context' debe incluir 'proposalId' JUNTO CON cada campo editable enlazado "
            "a su path, nunca copiado como texto fijo — así el backend recibe lo que el usuario "
            "realmente ajustó, no lo que el modelo cree que puso. "
            "Ejemplo completo (un Slider que ajusta un monto a apartar, con su botón de confirmar):\n"
            '{"version": "v0.9", "createSurface": {"surfaceId": "<id>", "catalogId": "..."}}\n'
            '{"version": "v0.9", "updateComponents": {"surfaceId": "<id>", "components": ['
            '{"id": "root", "component": "Card", "child": "col"}, '
            '{"id": "col", "component": "Column", "children": ["slider", "btn"]}, '
            '{"id": "slider", "component": "Slider", "label": "Monto a apartar", "min": 0, '
            '"max": 2000, "value": {"path": "/montoApartar"}}, '
            '{"id": "btn", "component": "Button", "child": "btnLabel", "variant": "primary", '
            '"action": {"event": {"name": "confirmar_accion", '
            '"context": {"proposalId": "abc-123", "monto": {"path": "/montoApartar"}}}}}, '
            '{"id": "btnLabel", "component": "Text", "text": "Confirmar"}]}}\n'
            '{"version": "v0.9", "updateDataModel": {"surfaceId": "<id>", "path": "/", '
            '"value": {"montoApartar": 500}}}\n'
            "No inventes datos que el usuario deba ajustar si no tienes un rango o valor inicial "
            "razonable: si no sabes min/max, pide el dato por texto en vez de mostrar un Slider a "
            "ciegas. "
            "OBLIGATORIO para 'proponer_contacto', 'proponer_gasto_fijo', 'proponer_ingreso_programado' "
            "y 'proponer_meta': la tarjeta de confirmación NUNCA muestra los datos propuestos como "
            "texto estático — cada campo va en un TextField (o DateTimeInput para una fecha, "
            "ChoicePicker para 'frecuencia') enlazado al data model, inicializado con tu propuesta "
            "como valor por default, para que el usuario pueda corregirlo antes de confirmar (nunca "
            "asumas que tu propuesta es correcta, en especial una cuenta destino o un monto). El "
            "'context' del botón debe usar EXACTAMENTE estas llaves además de 'proposalId', o el "
            "backend ignora la edición: contacto → nombre, alias, cuenta_destino, relacion; "
            "gasto_fijo → concepto, monto, frecuencia, proxima_fecha; ingreso_programado → "
            "descripcion, monto, frecuencia, proxima_fecha; meta → descripcion, monto_objetivo, "
            "fecha_objetivo. Además, agrega 'checks' al botón para que se deshabilite mientras falte "
            "un campo requerido: {\"condition\": {\"functionCall\": {\"call\": \"required\", \"args\": "
            "{\"value\": {\"path\": \"/nombre\"}}}}, \"message\": \"Falta el nombre\"} — uno por cada "
            "campo requerido de ese tipo. Nunca omitas 'checks' en estas 4 tarjetas: sin eso, el "
            "usuario puede confirmar con un campo vacío y el backend lo rechaza sin explicar por qué "
            "en la propia tarjeta. "
            "8) Además tienes 7 componentes propios de dominio financiero (no son parte del "
            "catálogo básico del protocolo, los diseñó este equipo) — úsalos para presentar datos "
            "reales de forma mucho más clara que un Text plano: "
            "StatCard muestra un dato destacado con tendencia (props: label, value ya formateado "
            "como texto, trend='up'|'down'|'flat' opcional, trendLabel opcional, tone="
            "'positive'|'negative'|'neutral'|'warning'). Úsalo con el resultado de "
            "'calcular_score_salud_financiera' (label='Salud financiera', value=f'{score}/100', "
            "tone según categoria: Saludable→positive, Atención→warning, Riesgo→negative, "
            "trendLabel=el primer factor) o con el saldo/margen proyectado de "
            "'simular_flujo_de_caja'. "
            "BarChart dibuja barras (props: title opcional, valuePrefix opcional ej '$', bars=lista "
            "de {label, value, tone opcional}). Cada barra se dibuja proporcional al valor MÁS "
            "GRANDE de la lista, así que TODAS las barras de un mismo BarChart deben ser la misma "
            "clase de cosa y comparables entre sí (ej. gasto de varias categorías en el mismo "
            "periodo) — nunca mezcles ingresos, gastos y metas de fechas o naturalezas distintas "
            "en un mismo BarChart: un monto grande y lejano (ej. una meta a varios meses) aplasta "
            "visualmente montos pequeños y urgentes (ej. una renta que vence en días), aunque sean "
            "más importantes. Úsalo SIEMPRE que 'get_resumen_movimientos' devuelva 2 o más "
            "categorías, con bars=[{label: categoria, value: total} por cada fila] — nunca "
            "inventes categorías o montos que la herramienta no devolvió. Para un calendario o "
            "resumen de próximos eventos financieros (ingresos programados, gastos fijos, metas), "
            "NO uses BarChart: lista cada grupo por separado con Text/Row simples (como ya haces "
            "para 'Próximos Ingresos', 'Gastos Fijos Próximos', 'Metas de Ahorro'), sin además "
            "resumirlos todos juntos en una sola gráfica de barras. Cuando "
            "muestres un BarChart de gastos por categoría, llama TAMBIÉN a "
            "'detectar_picos_gasto' con el mismo rango de fechas: por cada categoría que "
            "aparezca en su resultado, pon tone='negative' en esa barra si severidad='alta', o "
            "tone='warning' si severidad='media'; las categorías que no aparecen ahí van sin "
            "tone (o 'neutral'). Nunca marques una categoría como pico sin que "
            "'detectar_picos_gasto' la haya devuelto — no lo decidas tú a partir de qué tan alta "
            "se ve la barra. "
            "PlanDePago muestra una lista de alternativas seleccionables, como una tabla de planes "
            "(props: title y subtitle opcionales, options=lista de {id, label, detail, amount ya "
            "formateado, highlighted opcional}, selectedId enlazado a un path del data model igual "
            "que los demás componentes de entrada). Úsalo con 'apartado_sugerido' de "
            "'simular_flujo_de_caja' (una sola opción está bien: id='sugerido', "
            "label=f'{periodicidad}', detail=f'{num_periodos} periodos', "
            "amount=monto_por_periodo formateado) seguido de un Button normal cuya "
            "'action.event.context' lea ese mismo path — nunca inventes tasas, CAT ni plazos "
            "adicionales que la herramienta no calculó. "
            "LineChart dibuja una serie de puntos conectados por una línea (props: title y "
            "valuePrefix opcionales, points=lista de {label, value, tone opcional para marcar UN "
            "punto crítico}, thresholdValue/thresholdLabel opcionales para una línea de "
            "referencia horizontal). Úsalo SIEMPRE que 'simular_flujo_de_caja' devuelva su campo "
            "'serie': points=[{label: fecha formateada corta, value: saldo} por cada punto de la "
            "serie], marca con tone='negative' el punto cuya fecha coincida con 'fecha_critica', "
            "y si 'alcanza' es false pon thresholdValue=0, thresholdLabel='Saldo en $0'. Esto "
            "reemplaza el texto plano de '¿cómo se calculó?': muestra la gráfica en vez de (o "
            "además de) los montos en un Modal. Nunca inventes puntos intermedios que la "
            "herramienta no devolvió — usa la serie tal cual, en el mismo orden. "
            "ApartadoPlanner es un slider interactivo para ajustar un apartado de ahorro (props: "
            "title/subtitle opcionales, montoObjetivo=el déficit real en pesos, "
            "periodicidadLabel=ej 'semanal', minMonto/maxMonto para el rango del slider, "
            "montoPorPeriodo enlazado a un path del data model). El componente calcula SOLO en "
            "el navegador cuántos periodos hacen falta según lo que el usuario arrastre — tú "
            "nunca calculas eso, solo das montoObjetivo real (de 'apartado_sugerido' o del "
            "'margen' negativo de 'simular_flujo_de_caja') y un rango de minMonto/maxMonto "
            "razonable alrededor del monto_por_periodo sugerido (ej. la mitad y el doble). "
            "Ponlo seguido de un Button normal cuya 'action.event.context' lea el path de "
            "montoPorPeriodo para de verdad crear el apartado con ese monto ajustado. "
            "DonutChart muestra una proporción del total, no una comparación de barras "
            "independientes (props: title opcional, centerLabel/centerValue opcionales ya "
            "formateados, slices=lista de {id, label, value}, selectedId enlazado a un path para "
            "resaltar la porción que el usuario toque). Úsalo en vez de BarChart SOLO cuando el "
            "punto sea 'de qué está compuesto el 100% de X' (ej. distribución del gasto total del "
            "mes entre categorías); si el punto es comparar montos entre sí sin importar el total, "
            "usa BarChart. Mismo origen de datos que BarChart: 'get_resumen_movimientos', "
            "slices=[{id: categoria, label: categoria, value: total} por cada fila], "
            "centerValue=la suma de todos los totales ya formateada. Nunca inventes categorías. "
            "BudgetAllocator reparte un monto real entre destinos reales con un chip seleccionable "
            "más un slider (props: title/subtitle opcionales, total=monto real disponible, "
            "categorias=lista de {id, label} con AL MENOS 2 destinos reales, "
            "categoriaSeleccionada y montoAsignado enlazados a paths del data model). Úsalo con "
            "total='margen' de 'simular_flujo_de_caja' cuando sea positivo, y categorias tomadas "
            "de 'get_metas' (una entrada por meta activa, más una entrada final tipo "
            "{id: 'libre', label: 'Sin asignar'} si quieres dejar la opción de no apartarlo). El "
            "componente calcula SOLO en el navegador cuánto queda sin asignar de 'total' al mover "
            "el slider o cambiar de chip — tú nunca calculas eso. Ponlo seguido de un Button normal "
            "cuya 'action.event.context' lea categoriaSeleccionada y montoAsignado para de verdad "
            "crear el apartado en esa meta. "
            "Nunca uses estos 7 componentes como decoración de un dato que ya se explica solo con "
            "un Text; resérvalos para cuando de verdad ayudan a comparar, destacar o interactuar "
            "con información real."
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
            version=_VERSION, catalogs=[a2ui_custom_catalog.get_config(_VERSION)]
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

    async def _run_tool_loop(self, account_id: str, contents: list, conversacion_id: int) -> str:
        config = self._generate_content_config()

        for _ in range(MAX_TOOL_CALL_ROUNDS):
            response = self._client.models.generate_content(
                model=self._model, contents=contents, config=config
            )
            if not response.function_calls:
                return response.text

            contents.append(response.candidates[0].content)

            for call in response.function_calls:
                tool_result = await self._dispatch_tool_call(account_id, call, conversacion_id)
                contents.append(
                    types.Part.from_function_response(
                        name=call.name,
                        response=_as_function_response_payload(tool_result),
                    )
                )

        return ""

    async def _dispatch_tool_call(self, account_id: str, call, conversacion_id: int) -> Any:
        if call.name in _READ_ONLY_TOOLS:
            args = {"account_id": account_id}
            if call.name in ("get_resumen_movimientos", "detectar_picos_gasto"):
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
            return await self._proponer_transferencia(account_id, call.args, conversacion_id)

        if call.name == "proponer_apartado":
            return self._proponer_apartado(account_id, call.args, conversacion_id)

        if call.name == "proponer_contacto":
            return self._proponer_contacto(account_id, call.args, conversacion_id)

        if call.name == "proponer_gasto_fijo":
            return self._proponer_gasto_fijo(account_id, call.args, conversacion_id)

        if call.name == "proponer_ingreso_programado":
            return self._proponer_ingreso_programado(account_id, call.args, conversacion_id)

        if call.name == "proponer_meta":
            return self._proponer_meta(account_id, call.args, conversacion_id)

        return {"error": f"Herramienta no permitida: {call.name}"}

    async def _proponer_transferencia(self, account_id: str, args: dict, conversacion_id: int) -> dict:
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
            conversacion_id=conversacion_id,
        )
        return {"proposalId": proposal.id, "resumen": proposal.resumen}

    def _proponer_apartado(self, account_id: str, args: dict, conversacion_id: int) -> dict:
        args = args or {}
        meta_id = args.get("meta_id")
        if meta_id is None:
            return {"error": "Falta el argumento requerido: meta_id"}

        payload = {
            "meta_id": int(meta_id),
            "monto_por_periodo": args.get("monto_por_periodo"),
            "periodicidad": args.get("periodicidad"),
        }
        error = _validar_datos_creacion("apartado", payload)
        if error:
            return {"error": error}

        proposal = proposals.crear_propuesta(
            account_id=account_id,
            tipo="apartado",
            payload=payload,
            resumen=f"Apartar ${payload['monto_por_periodo']:.2f} {payload['periodicidad']} hacia tu meta",
            conversacion_id=conversacion_id,
        )
        return {"proposalId": proposal.id, "resumen": proposal.resumen}

    def _proponer_contacto(self, account_id: str, args: dict, conversacion_id: int) -> dict:
        payload = {
            "nombre": (args or {}).get("nombre"),
            "alias": (args or {}).get("alias"),
            "cuenta_destino": (args or {}).get("cuenta_destino"),
            "relacion": (args or {}).get("relacion"),
        }
        error = _validar_datos_creacion("contacto", payload)
        if error:
            return {"error": error}

        proposal = proposals.crear_propuesta(
            account_id=account_id,
            tipo="contacto",
            payload=payload,
            resumen=f"Agregar a {payload['nombre']} ({payload['alias']}) como contacto",
            conversacion_id=conversacion_id,
        )
        return {"proposalId": proposal.id, "resumen": proposal.resumen}

    def _proponer_gasto_fijo(self, account_id: str, args: dict, conversacion_id: int) -> dict:
        payload = {
            "concepto": (args or {}).get("concepto"),
            "monto": (args or {}).get("monto"),
            "frecuencia": (args or {}).get("frecuencia"),
            "proxima_fecha": (args or {}).get("proxima_fecha"),
        }
        error = _validar_datos_creacion("gasto_fijo", payload)
        if error:
            return {"error": error}

        proposal = proposals.crear_propuesta(
            account_id=account_id,
            tipo="gasto_fijo",
            payload=payload,
            resumen=f"Agregar gasto fijo: {payload['concepto']} (${payload['monto']:.2f} {payload['frecuencia']})",
            conversacion_id=conversacion_id,
        )
        return {"proposalId": proposal.id, "resumen": proposal.resumen}

    def _proponer_ingreso_programado(self, account_id: str, args: dict, conversacion_id: int) -> dict:
        payload = {
            "descripcion": (args or {}).get("descripcion"),
            "monto": (args or {}).get("monto"),
            "frecuencia": (args or {}).get("frecuencia"),
            "proxima_fecha": (args or {}).get("proxima_fecha"),
        }
        error = _validar_datos_creacion("ingreso_programado", payload)
        if error:
            return {"error": error}

        proposal = proposals.crear_propuesta(
            account_id=account_id,
            tipo="ingreso_programado",
            payload=payload,
            resumen=f"Agregar ingreso programado: {payload['descripcion']} (${payload['monto']:.2f} {payload['frecuencia']})",
            conversacion_id=conversacion_id,
        )
        return {"proposalId": proposal.id, "resumen": proposal.resumen}

    def _proponer_meta(self, account_id: str, args: dict, conversacion_id: int) -> dict:
        payload = {
            "descripcion": (args or {}).get("descripcion"),
            "monto_objetivo": (args or {}).get("monto_objetivo"),
            "fecha_objetivo": (args or {}).get("fecha_objetivo"),
        }
        error = _validar_datos_creacion("meta", payload)
        if error:
            return {"error": error}

        proposal = proposals.crear_propuesta(
            account_id=account_id,
            tipo="meta",
            payload=payload,
            conversacion_id=conversacion_id,
            resumen=f"Crear meta: {payload['descripcion']} (${payload['monto_objetivo']:.2f})",
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

    def generar_propuesta_sugerencia(self, titulo: str, descripcion: str) -> str:
        # Bajo demanda (nunca automático al abrir la tab "Atención"): la
        # detección de la sugerencia es 100% determinista (sugerencias_engine.py,
        # ver ADR 0019), pero elaborar una recomendación de qué hacer con ese
        # hecho sí es una tarea de lenguaje natural razonable para el LLM,
        # siempre y cuando reciba los hechos ya calculados como único
        # contexto y no pueda inventar cifras nuevas. Es una llamada de una
        # sola vuelta (sin tools, sin A2UI) — no reusa _run_tool_loop.
        prompt = (
            f"Detectamos lo siguiente en la cuenta del usuario: '{titulo}: {descripcion}'. "
            "En 1-2 oraciones, en español, sugiere una acción concreta y realista que el "
            "usuario podría tomar al respecto. Nunca inventes montos, fechas u otros datos "
            "que no te dimos aquí: solo elabora sobre estos hechos. No repitas el dato tal "
            "cual, ve directo a la recomendación."
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=[prompt],
            config=types.GenerateContentConfig(
                system_instruction=(
                    "Eres el asistente financiero de un banco. Respondes SIEMPRE en texto "
                    "plano y breve, nunca en JSON ni A2UI."
                ),
            ),
        )
        return (response.text or "").strip()

    async def confirm_action(
        self, account_id: str, proposal_id: str, context: dict | None = None
    ) -> list[dict]:
        proposal = proposals.obtener_propuesta_valida(proposal_id, account_id)
        if proposal is None:
            return error_a2ui_block(
                "La propuesta no existe, no te pertenece, o expiró. Pídela de nuevo."
            )

        # `context` trae lo que el usuario haya corregido en la tarjeta (ej. un
        # TextField con el nombre o la cuenta destino) antes de tocar
        # "Confirmar" — ver ADR 0009. Solo se aceptan los campos editables de
        # ESE tipo de propuesta (_CAMPOS_EDITABLES_AL_CONFIRMAR): nunca
        # account_id ni ids de referencia como meta_id/contacto_id, que no
        # vienen de un campo de texto y aceptar un override ahí reabriría el
        # hueco que proponer/confirmar existe para cerrar. Se valida ANTES de
        # descartar la propuesta: si el usuario borró un campo requerido, la
        # tarjeta sigue viva para que lo corrija y confirme de nuevo, en vez
        # de quemar la propuesta por un error que el botón ya debería haber
        # bloqueado del lado del cliente (ver `checks` en el system prompt).
        payload = proposal.payload
        campos_editables = _CAMPOS_EDITABLES_AL_CONFIRMAR.get(proposal.tipo)
        if campos_editables and context:
            payload = dict(proposal.payload)
            for campo in campos_editables:
                if campo in context:
                    payload[campo] = context[campo]
            error = _validar_datos_creacion(proposal.tipo, payload)
            if error:
                return error_a2ui_block(error)

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
                        "meta_id": payload["meta_id"],
                        "monto_por_periodo": payload["monto_por_periodo"],
                        "periodicidad": payload["periodicidad"],
                    },
                )
                return await self._responder_confirmacion(
                    account_id,
                    proposal,
                    f"Apartado de ${payload['monto_por_periodo']:.2f} {payload['periodicidad']} activado correctamente.",
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
                return await self._responder_confirmacion(
                    account_id,
                    proposal,
                    f"Transferencia realizada. Nuevo saldo: ${resultado['nuevo_saldo']:.2f}",
                )

            if proposal.tipo == "contacto":
                await self._mcp.call(
                    "crear_contacto",
                    {
                        "account_id": account_id,
                        "nombre": payload["nombre"],
                        "alias": payload["alias"],
                        "cuenta_destino": payload["cuenta_destino"],
                        "relacion": payload["relacion"],
                    },
                )
                return await self._responder_confirmacion(
                    account_id, proposal, f"Contacto {payload['nombre']} agregado correctamente."
                )

            if proposal.tipo == "gasto_fijo":
                await self._mcp.call(
                    "crear_gasto_fijo",
                    {
                        "account_id": account_id,
                        "concepto": payload["concepto"],
                        "monto": payload["monto"],
                        "frecuencia": payload["frecuencia"],
                        "proxima_fecha": payload["proxima_fecha"],
                    },
                )
                return await self._responder_confirmacion(
                    account_id, proposal, f"Gasto fijo '{payload['concepto']}' agregado correctamente."
                )

            if proposal.tipo == "ingreso_programado":
                await self._mcp.call(
                    "crear_ingreso_programado",
                    {
                        "account_id": account_id,
                        "descripcion": payload["descripcion"],
                        "monto": payload["monto"],
                        "frecuencia": payload["frecuencia"],
                        "proxima_fecha": payload["proxima_fecha"],
                    },
                )
                return await self._responder_confirmacion(
                    account_id,
                    proposal,
                    f"Ingreso programado '{payload['descripcion']}' agregado correctamente.",
                )

            if proposal.tipo == "meta":
                await self._mcp.call(
                    "crear_meta",
                    {
                        "account_id": account_id,
                        "descripcion": payload["descripcion"],
                        "monto_objetivo": payload["monto_objetivo"],
                        "fecha_objetivo": payload["fecha_objetivo"],
                    },
                )
                return await self._responder_confirmacion(
                    account_id, proposal, f"Meta '{payload['descripcion']}' creada correctamente."
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

    async def reject_action(self, account_id: str, proposal_id: str) -> list[dict]:
        # El otro lado del patrón proponer/confirmar (ADR 0009): hasta ahora
        # "rechazar" solo era "no tocar el botón" — no había ninguna acción
        # explícita, ni quedaba registro de que el usuario decidió NO seguir.
        # Comparte la propuesta con confirm_action, así que el chequeo de
        # dueño/expiración y la persistencia en el hilo son los mismos.
        proposal = proposals.obtener_propuesta_valida(proposal_id, account_id)
        if proposal is None:
            return error_a2ui_block(
                "La propuesta no existe, no te pertenece, o expiró. Pídela de nuevo."
            )
        proposals.descartar_propuesta(proposal_id)
        return await self._responder_confirmacion(account_id, proposal, f"Cancelado: {proposal.resumen}.")

    async def _responder_confirmacion(
        self, account_id: str, proposal: proposals.Proposal, mensaje: str
    ) -> list[dict]:
        # La acción real (crear_contacto, ejecutar_transferencia, etc.) ya se
        # ejecutó cuando esto se llama. Persistir el resultado en el hilo
        # donde se propuso es lo único que hace que reabrir esa conversación
        # después muestre si de verdad se autorizó, en vez de solo la
        # tarjeta original — que sin esto se ve idéntica confirmada o no.
        # Si falta conversacion_id (no debería, toda propuesta hoy nace
        # dentro de un chat) o si el guardado falla, la acción YA ocurrió de
        # verdad: nunca se convierte ese fallo en un error de vuelta al
        # usuario, solo se registra (mismo criterio que handle_message usa
        # para sus propios `agregar_mensaje_conversacion`).
        bloque = _confirmation_a2ui_block(mensaje)
        if proposal.conversacion_id is not None:
            try:
                await self._mcp.call(
                    "agregar_mensaje_conversacion",
                    {
                        "account_id": account_id,
                        "conversacion_id": proposal.conversacion_id,
                        "rol": "model",
                        "contenido": _a2ui_block_to_raw_text(bloque),
                    },
                )
            except Exception:  # noqa: BLE001 - ver comentario arriba
                _logger.exception("No se pudo persistir la confirmación en el historial")
        return bloque

    def reparsear_mensaje_modelo(self, contenido: str) -> list[dict] | None:
        # Los turnos "model" persistidos en una conversación guardan el texto
        # crudo que produjo el LLM (el mismo que se le reenvía como historial
        # en el próximo turno), no el bloque A2UI ya parseado que ve el
        # frontend en vivo. Al abrir un historial pasado, esta función corre
        # el mismo parser que handle_message para reconstruir esa tarjeta con
        # fidelidad completa (misma tarjeta interactiva), en vez de mostrarla
        # como texto plano.
        try:
            parts = self._fmt.parser.parse_response(contenido)
        except Exception:  # noqa: BLE001 - un mensaje viejo mal formado no debe tirar el historial completo
            return None
        for part in parts:
            if part.a2ui_json:
                return _rewrite_surface_id(part.a2ui_json, _new_surface_id())
        return None

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
                final_text = await self._run_tool_loop(account_id, contents, conversacion_id)

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
