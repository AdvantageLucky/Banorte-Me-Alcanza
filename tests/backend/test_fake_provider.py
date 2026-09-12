import json
import re

from me_alcanza.backend import fake_provider


def _extraer_a2ui(texto: str) -> list[dict]:
    match = re.search(r"<a2ui-json>(.*?)</a2ui-json>", texto, re.DOTALL)
    assert match is not None, "la respuesta offline debe traer un bloque <a2ui-json>"
    return json.loads(match.group(1))


def test_saldo_devuelve_tarjeta_de_saldo():
    texto = fake_provider.generar_respuesta_offline("¿cuál es mi saldo?")
    bloques = _extraer_a2ui(texto)
    assert any("createSurface" in b for b in bloques)
    valores = next(b for b in bloques if "updateDataModel" in b)["updateDataModel"]["value"]
    assert "offline" in json.dumps(valores).lower()


def test_meta_devuelve_tarjeta_de_metas():
    texto = fake_provider.generar_respuesta_offline("quiero ver mis metas de ahorro")
    bloques = _extraer_a2ui(texto)
    assert any("createSurface" in b for b in bloques)


def test_mensaje_generico_sin_keyword_conocida():
    texto = fake_provider.generar_respuesta_offline("cuéntame un chiste")
    bloques = _extraer_a2ui(texto)
    valores = next(b for b in bloques if "updateDataModel" in b)["updateDataModel"]["value"]
    assert "offline" in json.dumps(valores).lower()
