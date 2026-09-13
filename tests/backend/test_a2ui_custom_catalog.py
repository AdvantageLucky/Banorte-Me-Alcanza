"""Valida los componentes de dominio del catálogo propio contra el parser/
validador REAL de a2ui (no una copia a mano del schema) — el mismo código
que usa Orchestrator para aceptar o rechazar la respuesta del modelo.
"""

from a2ui.inference_formats.direct_json.format import DirectJsonFormat

from me_alcanza.backend import a2ui_custom_catalog

_CID = a2ui_custom_catalog.CUSTOM_CATALOG_ID
_FMT = DirectJsonFormat(version="0.9", catalogs=[a2ui_custom_catalog.get_config("0.9")])


def _parse(components_json: str, data_model_json: str = "{}"):
    texto = (
        "texto\n<a2ui-json>\n[\n"
        f'  {{"version": "v0.9", "createSurface": {{"surfaceId": "s1", "catalogId": "{_CID}"}}}},\n'
        f'  {{"version": "v0.9", "updateComponents": {{"surfaceId": "s1", "components": {components_json}}}}},\n'
        f'  {{"version": "v0.9", "updateDataModel": {{"surfaceId": "s1", "path": "/", "value": {data_model_json}}}}}\n'
        "]\n</a2ui-json>\n"
    )
    return _FMT.parser.parse_response(texto)


def test_line_chart_valido_parsea_sin_error():
    components = """[
        {"id": "root", "component": "Card", "child": "chart"},
        {"id": "chart", "component": "LineChart", "title": "Proyección", "points": [
            {"label": "11 sep", "value": 500},
            {"label": "15 sep", "value": -570, "tone": "negative"}
        ], "thresholdValue": 0, "thresholdLabel": "Saldo en $0"}
    ]"""
    parts = _parse(components)
    assert len(parts) == 1
    assert parts[0].a2ui_json is not None


def test_line_chart_sin_points_es_rechazado():
    components = """[
        {"id": "root", "component": "Card", "child": "chart"},
        {"id": "chart", "component": "LineChart", "title": "Proyección"}
    ]"""
    try:
        _parse(components)
        raise AssertionError("se esperaba que el parser rechazara un LineChart sin 'points'")
    except Exception as exc:  # noqa: BLE001
        assert "points" in str(exc) or "required" in str(exc).lower()


def test_line_chart_con_un_solo_point_es_rechazado():
    # minItems: 2 — una línea necesita al menos dos puntos para ser una línea.
    components = """[
        {"id": "root", "component": "Card", "child": "chart"},
        {"id": "chart", "component": "LineChart", "points": [{"label": "11 sep", "value": 500}]}
    ]"""
    try:
        _parse(components)
        raise AssertionError("se esperaba que el parser rechazara un LineChart con un solo punto")
    except Exception:  # noqa: BLE001
        pass


def test_apartado_planner_valido_parsea_sin_error():
    components = """[
        {"id": "root", "component": "Card", "child": "planner"},
        {"id": "planner", "component": "ApartadoPlanner", "title": "Ajusta tu apartado",
         "montoObjetivo": 570, "periodicidadLabel": "semanal", "minMonto": 50, "maxMonto": 300,
         "montoPorPeriodo": {"path": "/montoPorPeriodo"}}
    ]"""
    parts = _parse(components, data_model_json='{"montoPorPeriodo": 142.5}')
    assert len(parts) == 1
    assert parts[0].a2ui_json is not None


def test_apartado_planner_sin_monto_objetivo_es_rechazado():
    components = """[
        {"id": "root", "component": "Card", "child": "planner"},
        {"id": "planner", "component": "ApartadoPlanner", "periodicidadLabel": "semanal",
         "minMonto": 50, "maxMonto": 300, "montoPorPeriodo": {"path": "/montoPorPeriodo"}}
    ]"""
    try:
        _parse(components, data_model_json='{"montoPorPeriodo": 142.5}')
        raise AssertionError("se esperaba que el parser rechazara un ApartadoPlanner sin montoObjetivo")
    except Exception:  # noqa: BLE001
        pass


def test_donut_chart_valido_parsea_sin_error():
    components = """[
        {"id": "root", "component": "Card", "child": "donut"},
        {"id": "donut", "component": "DonutChart", "title": "Gasto por categoría",
         "centerLabel": "Total", "centerValue": "$4,530.00", "slices": [
            {"id": "renta", "label": "Renta", "value": 4500},
            {"id": "internet", "label": "Internet", "value": 599}
         ], "selectedId": {"path": "/categoriaResaltada"}}
    ]"""
    parts = _parse(components, data_model_json='{"categoriaResaltada": "renta"}')
    assert len(parts) == 1
    assert parts[0].a2ui_json is not None


def test_donut_chart_con_una_sola_porcion_es_rechazado():
    # minItems: 2 — una dona con una sola porción no comunica proporción.
    components = """[
        {"id": "root", "component": "Card", "child": "donut"},
        {"id": "donut", "component": "DonutChart", "slices": [{"id": "renta", "label": "Renta", "value": 4500}]}
    ]"""
    try:
        _parse(components)
        raise AssertionError("se esperaba que el parser rechazara un DonutChart con una sola porción")
    except Exception:  # noqa: BLE001
        pass


def test_budget_allocator_valido_parsea_sin_error():
    components = """[
        {"id": "root", "component": "Card", "child": "allocator"},
        {"id": "allocator", "component": "BudgetAllocator", "title": "Reparte tu margen",
         "total": 1200, "categorias": [
            {"id": "laptop", "label": "Laptop nueva"},
            {"id": "libre", "label": "Sin asignar"}
         ], "categoriaSeleccionada": {"path": "/categoriaSeleccionada"},
         "montoAsignado": {"path": "/montoAsignado"}}
    ]"""
    parts = _parse(
        components,
        data_model_json='{"categoriaSeleccionada": "laptop", "montoAsignado": 500}',
    )
    assert len(parts) == 1
    assert parts[0].a2ui_json is not None


def test_budget_allocator_sin_total_es_rechazado():
    components = """[
        {"id": "root", "component": "Card", "child": "allocator"},
        {"id": "allocator", "component": "BudgetAllocator", "categorias": [
            {"id": "laptop", "label": "Laptop nueva"},
            {"id": "libre", "label": "Sin asignar"}
         ], "categoriaSeleccionada": {"path": "/categoriaSeleccionada"},
         "montoAsignado": {"path": "/montoAsignado"}}
    ]"""
    try:
        _parse(
            components,
            data_model_json='{"categoriaSeleccionada": "laptop", "montoAsignado": 500}',
        )
        raise AssertionError("se esperaba que el parser rechazara un BudgetAllocator sin total")
    except Exception:  # noqa: BLE001
        pass
