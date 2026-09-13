import uuid
from datetime import datetime

from . import a2ui_custom_catalog

_VERSION = "0.9"  # solo para BasicCatalog.get_catalog_id
# El envelope A2UI exige el prefijo "v": a2ui_core (Flutter) rechaza "0.9".
_ENVELOPE_VERSION = "v0.9"

_MESES_ABREV = {
    1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
    7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic",
}


def _catalog_id() -> str:
    return a2ui_custom_catalog.CUSTOM_CATALOG_ID


def _new_surface_id() -> str:
    return f"sugerencia-{uuid.uuid4().hex[:8]}"


def _formatear_monto(monto: float) -> str:
    return f"${monto:,.2f}"


def _formatear_fecha(fecha_iso: str) -> str:
    fecha = datetime.strptime(fecha_iso, "%Y-%m-%d").date()
    return f"{fecha.day:02d} {_MESES_ABREV[fecha.month]} {fecha.year}"


def titulo_y_descripcion(tipo: str, detalle: dict) -> tuple[str, str]:
    # Se usa para el resumen de texto plano del modal HITL de "Atender" (ver
    # extractSugerenciaCopy.js: recombina lo que aquí se separa en label/
    # value/trendLabel del StatCard). La tarjeta que ve el usuario en el feed
    # ya no usa este texto tal cual: usa un StatCard (ver
    # _stat_card_props/construir_tarjeta_sugerencia).
    if tipo == "riesgo_liquidez":
        return (
            "Riesgo de saldo negativo",
            f"Tu saldo podría quedar en {_formatear_monto(detalle['margen'])} "
            f"para el {_formatear_fecha(detalle['fecha_critica'])}.",
        )
    if tipo == "gasto_fijo_proximo":
        return (
            f"Pago próximo: {detalle['concepto']}",
            f"{_formatear_monto(detalle['monto'])} vence el {_formatear_fecha(detalle['proxima_fecha'])} "
            "y es una parte importante de tu saldo actual.",
        )
    if tipo == "meta_en_riesgo":
        return (
            f"Meta en riesgo: {detalle['descripcion']}",
            f"Llevas {_formatear_monto(detalle['monto_ahorrado'])} de "
            f"{_formatear_monto(detalle['monto_objetivo'])} y la fecha límite es el "
            f"{_formatear_fecha(detalle['fecha_objetivo'])}.",
        )
    return ("Sugerencia", "")


def _stat_card_props(tipo: str, detalle: dict) -> dict:
    # El dato destacado de cada tipo de sugerencia, para el StatCard que
    # reemplaza el texto plano en la tarjeta del feed (ver
    # construir_tarjeta_sugerencia) — mismo StatCard que ya usa el LLM en el
    # chat (a2ui_custom_catalog.py), para que "Atención" no se sienta como
    # un feed de texto aparte sino como la misma UI generativa.
    if tipo == "riesgo_liquidez":
        return {
            "label": "Saldo proyectado",
            "value": _formatear_monto(detalle["margen"]),
            "trendLabel": f"para el {_formatear_fecha(detalle['fecha_critica'])}",
            "tone": "negative",
        }
    if tipo == "gasto_fijo_proximo":
        return {
            "label": detalle["concepto"],
            "value": _formatear_monto(detalle["monto"]),
            "trendLabel": (
                f"vence el {_formatear_fecha(detalle['proxima_fecha'])} y es una parte "
                "importante de tu saldo actual"
            ),
            "tone": "warning",
        }
    if tipo == "meta_en_riesgo":
        return {
            "label": detalle["descripcion"],
            "value": (
                f"{_formatear_monto(detalle['monto_ahorrado'])} de "
                f"{_formatear_monto(detalle['monto_objetivo'])}"
            ),
            "trendLabel": f"fecha límite {_formatear_fecha(detalle['fecha_objetivo'])}",
            "tone": "warning",
        }
    return {"label": "Sugerencia", "value": "", "tone": "neutral"}


def construir_tarjeta_sugerencia(sugerencia: dict) -> list[dict]:
    # Determinista, no generada por el LLM: misma garantía de seguridad que
    # 'proponer_x'/'confirmar_accion' -el usuario nunca confirma/descarta
    # contra un texto que el modelo pudo haber alucinado, porque el modelo
    # nunca participa en armar esto.
    titulo, _ = titulo_y_descripcion(sugerencia["tipo"], sugerencia["detalle"])
    stat_props = _stat_card_props(sugerencia["tipo"], sugerencia["detalle"])
    surface_id = _new_surface_id()
    sugerencia_id = sugerencia["id"]
    return [
        {"version": _ENVELOPE_VERSION, "createSurface": {"surfaceId": surface_id, "catalogId": _catalog_id()}},
        {
            "version": _ENVELOPE_VERSION,
            "updateComponents": {
                "surfaceId": surface_id,
                "components": [
                    {"id": "root", "component": "Card", "child": "col"},
                    {"id": "col", "component": "Column", "children": ["titulo", "stat", "botones"]},
                    {"id": "titulo", "component": "Text", "text": titulo, "variant": "h3"},
                    {"id": "stat", "component": "StatCard", **stat_props},
                    {
                        "id": "botones",
                        "component": "Row",
                        "justify": "end",
                        "children": ["btn_descartar", "btn_atender"],
                    },
                    {
                        "id": "btn_descartar",
                        "component": "Button",
                        "variant": "borderless",
                        "child": "btn_descartar_text",
                        "action": {
                            "event": {
                                "name": "descartar_sugerencia",
                                "context": {"sugerenciaId": sugerencia_id},
                            }
                        },
                    },
                    {"id": "btn_descartar_text", "component": "Text", "text": "Descartar", "variant": "body"},
                    {
                        "id": "btn_atender",
                        "component": "Button",
                        "variant": "primary",
                        "child": "btn_atender_text",
                        "action": {
                            "event": {
                                "name": "atender_sugerencia",
                                "context": {"sugerenciaId": sugerencia_id},
                            }
                        },
                    },
                    {"id": "btn_atender_text", "component": "Text", "text": "Atender", "variant": "body"},
                ],
            },
        },
    ]
