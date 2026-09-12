import time

import pytest

from me_alcanza.backend import proposals


@pytest.fixture(autouse=True)
def _clear_proposals():
    proposals.PROPOSALS.clear()
    yield
    proposals.PROPOSALS.clear()


def test_crear_propuesta_genera_id_unico_y_la_guarda():
    p1 = proposals.crear_propuesta("ana", "apartado", {"meta_id": 1}, "Apartar $100")
    p2 = proposals.crear_propuesta("ana", "apartado", {"meta_id": 1}, "Apartar $100")
    assert p1.id != p2.id
    assert proposals.PROPOSALS[p1.id] is p1
    assert proposals.PROPOSALS[p2.id] is p2


def test_obtener_propuesta_valida_ok():
    p = proposals.crear_propuesta("ana", "transferencia", {"monto": 500}, "Transferir $500")
    assert proposals.obtener_propuesta_valida(p.id, "ana") is p


def test_obtener_propuesta_valida_cuenta_distinta_devuelve_none():
    p = proposals.crear_propuesta("ana", "transferencia", {"monto": 500}, "Transferir $500")
    assert proposals.obtener_propuesta_valida(p.id, "luis") is None
    # no se elimina solo por consultarla con otra cuenta
    assert p.id in proposals.PROPOSALS


def test_obtener_propuesta_valida_inexistente_devuelve_none():
    assert proposals.obtener_propuesta_valida("no-existe", "ana") is None


def test_obtener_propuesta_valida_expirada_devuelve_none_y_la_elimina():
    p = proposals.crear_propuesta("ana", "apartado", {"meta_id": 1}, "Apartar $100")
    p.created_at = time.time() - proposals.PROPOSAL_TTL_SECONDS - 1
    assert proposals.obtener_propuesta_valida(p.id, "ana") is None
    assert p.id not in proposals.PROPOSALS


def test_descartar_propuesta_la_elimina():
    p = proposals.crear_propuesta("ana", "apartado", {"meta_id": 1}, "Apartar $100")
    proposals.descartar_propuesta(p.id)
    assert p.id not in proposals.PROPOSALS


def test_descartar_propuesta_inexistente_no_lanza_error():
    proposals.descartar_propuesta("no-existe")
