"""Catálogo A2UI propio del equipo.

El reto exige explícitamente que "el sistema de componentes que el agente
invoca lo diseña y programa el equipo" (no se entrega una biblioteca de UI).
Este módulo construye ESE catálogo: toma como base los primitivos del
catálogo básico de la especificación A2UI (Card, Text, Button, etc. — la
gramática mínima del protocolo) y le agrega componentes de dominio
financiero diseñados por nosotros (StatCard, BarChart, PlanDePago).

El resultado es un único catálogo, con un catalogId propio, que es lo que
Orchestrator usa tanto para generar el prompt (JSON Schema completo) como
para validar/parsear la respuesta del modelo.

Su contraparte en JS vive en frontend/src/a2ui-custom/catalog.js: los
nombres de componente y de props deben coincidir a mano entre ambos lados,
no hay generación automática entre este schema y esa implementación React.
"""

import copy
from typing import Any

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.catalog import CatalogConfig
from a2ui.schema.catalog_provider import A2uiCatalogProvider

CUSTOM_CATALOG_ID = "https://me-alcanza.hackmty.dev/catalogs/v1/catalog.json"

_COMMON_TYPES = "https://a2ui.org/specification/v0_9/common_types.json"


def _dynamic_string(**extra: Any) -> dict[str, Any]:
    return {"$ref": f"{_COMMON_TYPES}#/$defs/DynamicString", **extra}


def _component_common() -> dict[str, Any]:
    return {"$ref": f"{_COMMON_TYPES}#/$defs/ComponentCommon"}


def _stat_card_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "allOf": [
            _component_common(),
            {
                "type": "object",
                "properties": {
                    "component": {"const": "StatCard"},
                    "label": _dynamic_string(description="Etiqueta corta del dato (ej. 'Salud financiera')."),
                    "value": _dynamic_string(
                        description="El valor destacado, ya formateado como texto (ej. '82/100', '$4,230.00')."
                    ),
                    "trend": {
                        "type": "string",
                        "enum": ["up", "down", "flat"],
                        "description": "Dirección de la tendencia respecto a un periodo o umbral de referencia.",
                    },
                    "trendLabel": _dynamic_string(
                        description="Texto corto junto a la tendencia (ej. 'Mejoró vs el mes pasado')."
                    ),
                    "tone": {
                        "type": "string",
                        "enum": ["positive", "negative", "neutral", "warning"],
                        "default": "neutral",
                        "description": "Color de acento: positive/negative/warning según si el dato es buena o mala noticia.",
                    },
                    "weight": {"type": "number"},
                },
                "required": ["component", "label", "value"],
            },
        ],
        "unevaluatedProperties": False,
    }


def _bar_chart_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "allOf": [
            _component_common(),
            {
                "type": "object",
                "properties": {
                    "component": {"const": "BarChart"},
                    "title": _dynamic_string(description="Título opcional sobre la gráfica."),
                    "valuePrefix": {
                        "type": "string",
                        "description": "Prefijo para cada valor mostrado (ej. '$'). Vacío si no aplica.",
                    },
                    "bars": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "value": {"type": "number"},
                                "tone": {
                                    "type": "string",
                                    "enum": ["positive", "negative", "neutral", "warning"],
                                },
                            },
                            "required": ["label", "value"],
                            "additionalProperties": False,
                        },
                        "description": (
                            "Barras a graficar. SIEMPRE con datos reales devueltos por una "
                            "herramienta (ej. get_resumen_movimientos), nunca inventados."
                        ),
                    },
                    "weight": {"type": "number"},
                },
                "required": ["component", "bars"],
            },
        ],
        "unevaluatedProperties": False,
    }


def _plan_de_pago_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "allOf": [
            _component_common(),
            {
                "type": "object",
                "properties": {
                    "component": {"const": "PlanDePago"},
                    "title": _dynamic_string(description="Título del selector (ej. 'Elige tu plan')."),
                    "subtitle": _dynamic_string(description="Aclaración corta debajo del título."),
                    "options": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "description": "Id estable de esta opción."},
                                "label": {"type": "string", "description": "Ej. '12 meses'."},
                                "detail": {"type": "string", "description": "Ej. 'CAT 32.4%' o 'semanal'."},
                                "amount": {
                                    "type": "string",
                                    "description": "Monto ya formateado como texto (ej. '$1,690.00').",
                                },
                                "highlighted": {
                                    "type": "boolean",
                                    "description": "Marca esta opción como la recomendada.",
                                },
                            },
                            "required": ["id", "label", "detail", "amount"],
                            "additionalProperties": False,
                        },
                        "description": (
                            "Alternativas concretas con montos ya calculados por una herramienta "
                            "o derivados directamente de sus datos. Nunca inventes tasas, CAT o "
                            "plazos que no tengas."
                        ),
                    },
                    "selectedId": _dynamic_string(
                        description=(
                            "Id de la opción seleccionada, enlazado a un path del data model "
                            "(ej. {'path': '/planSeleccionado'}) para que un Button posterior "
                            "pueda leerlo."
                        )
                    ),
                    "weight": {"type": "number"},
                },
                "required": ["component", "options", "selectedId"],
            },
        ],
        "unevaluatedProperties": False,
    }


def _build_catalog_schema(version: str) -> dict[str, Any]:
    base = copy.deepcopy(BasicCatalog.get_config(version=version).provider.load())
    base["$id"] = CUSTOM_CATALOG_ID
    base["catalogId"] = CUSTOM_CATALOG_ID
    base["title"] = "Catálogo ¿Me Alcanza?"
    base["description"] = (
        "Catálogo propio del equipo: primitivos base del protocolo A2UI más "
        "componentes de dominio financiero (StatCard, BarChart, PlanDePago) "
        "diseñados y programados por el equipo, no una biblioteca de UI "
        "entregada por el reto."
    )
    base["components"]["StatCard"] = _stat_card_schema()
    base["components"]["BarChart"] = _bar_chart_schema()
    base["components"]["PlanDePago"] = _plan_de_pago_schema()

    any_component = base["$defs"]["anyComponent"]
    any_component["oneOf"].extend(
        [
            {"$ref": "#/components/StatCard"},
            {"$ref": "#/components/BarChart"},
            {"$ref": "#/components/PlanDePago"},
        ]
    )
    return base


class _CustomCatalogProvider(A2uiCatalogProvider):
    def __init__(self, version: str):
        self._version = version

    def load(self) -> dict[str, Any]:
        return _build_catalog_schema(self._version)


def get_config(version: str) -> CatalogConfig:
    """Devuelve el CatalogConfig combinado (básico + propio) para 'version'."""
    return CatalogConfig(name="me_alcanza", provider=_CustomCatalogProvider(version))
