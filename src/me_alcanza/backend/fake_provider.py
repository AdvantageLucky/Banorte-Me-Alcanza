import json

_CATALOG_ID = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"
_SURFACE_ID = "modo-offline"


def _bloque(mensaje: str) -> str:
    a2ui = [
        {"version": "v0.9", "createSurface": {"surfaceId": _SURFACE_ID, "catalogId": _CATALOG_ID}},
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": _SURFACE_ID,
                "components": [
                    {"id": "root", "component": "Card", "child": "col"},
                    {"id": "col", "component": "Column", "children": ["titulo", "msg"]},
                    {"id": "titulo", "component": "Text", "text": "Modo offline", "variant": "h3"},
                    {"id": "msg", "component": "Text", "text": {"path": "/mensaje"}},
                ],
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {"surfaceId": _SURFACE_ID, "path": "/", "value": {"mensaje": mensaje}},
        },
    ]
    return f"<a2ui-json>\n{json.dumps(a2ui)}\n</a2ui-json>"


def generar_respuesta_offline(mensaje: str) -> str:
    texto = mensaje.lower()
    if "saldo" in texto:
        return _bloque(
            "Modo offline: no puedo consultar tu saldo real en este momento. "
            "Este es un dato de ejemplo, no tu saldo verdadero."
        )
    if "meta" in texto or "ahorro" in texto:
        return _bloque(
            "Modo offline: no puedo consultar tus metas reales en este momento. "
            "Intenta de nuevo cuando el servicio esté disponible."
        )
    return _bloque(
        "Estamos en modo offline temporalmente y no podemos procesar tu solicitud ahora mismo. "
        "Intenta de nuevo en unos momentos."
    )
