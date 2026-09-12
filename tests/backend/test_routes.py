from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from me_alcanza.backend.app import create_app
from me_alcanza.backend import proposals


@pytest.fixture(autouse=True)
def _clear_proposals():
    proposals.PROPOSALS.clear()
    yield
    proposals.PROPOSALS.clear()


@pytest.fixture
def app(tmp_path):
    genai_client = MagicMock()
    return create_app(
        genai_client=genai_client,
        model="gemini-test",
        jwt_secret="test-secret-that-is-long-enough-for-pyjwt-hs256",
        db_path=str(tmp_path / "test_banco.db"),
    )


def test_login_credenciales_correctas_devuelve_token(app):
    with TestClient(app) as client:
        response = client.post("/api/login", json={"username": "ana", "password": "pass123"})
        assert response.status_code == 200
        assert "token" in response.json()


def test_login_credenciales_incorrectas_devuelve_401(app):
    with TestClient(app) as client:
        response = client.post("/api/login", json={"username": "ana", "password": "mala"})
        assert response.status_code == 401


def test_login_falla_del_mcp_devuelve_error_limpio_no_500_crudo(app):
    with TestClient(app) as client:
        # Forzamos una falla del lado del MCP (no credenciales inválidas, que
        # devuelven None): si login() no tuviera el try/except, TestClient
        # dejaría escapar esta excepción sin manejar en vez de una respuesta.
        app.state.mcp_client.call = AsyncMock(side_effect=RuntimeError("mcp caído"))
        response = client.post("/api/login", json={"username": "ana", "password": "pass123"})
        assert response.status_code == 503
        assert "mcp caído" not in response.text


def test_chat_sin_token_devuelve_401(app):
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"mensaje": "hola"})
        assert response.status_code == 401


def test_chat_con_token_llama_al_orquestador(app):
    with TestClient(app) as client:
        login = client.post("/api/login", json={"username": "ana", "password": "pass123"})
        token = login.json()["token"]

        fake_messages = [{"version": "v0.9", "createSurface": {"surfaceId": "main", "catalogId": "x"}}]
        app.state.orchestrator.handle_message = AsyncMock(return_value=fake_messages)

        response = client.post(
            "/api/chat",
            json={"mensaje": "¿me alcanza para el concierto?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json() == {"a2ui_messages": fake_messages}
        app.state.orchestrator.handle_message.assert_awaited_once()
        args = app.state.orchestrator.handle_message.await_args.args
        assert args[0] == "ana"
        assert args[2] == "¿me alcanza para el concierto?"


def test_chat_sin_conversacion_id_falla_del_mcp_al_autocrear_devuelve_400(app):
    with TestClient(app) as client:
        token = _login(client)

        async def fake_call(name, args=None):
            if name == "crear_conversacion":
                raise RuntimeError("mcp caído")
            return None

        app.state.mcp_client.call = AsyncMock(side_effect=fake_call)
        response = client.post(
            "/api/chat", json={"mensaje": "hola"}, headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 400
        assert "mcp caído" in response.json()["detail"]


def test_confirm_action_sin_token_devuelve_401(app):
    with TestClient(app) as client:
        response = client.post("/api/confirm-action", json={"proposal_id": "x"})
        assert response.status_code == 401


def test_confirm_action_con_token_llama_al_orquestador(app):
    with TestClient(app) as client:
        login = client.post("/api/login", json={"username": "ana", "password": "pass123"})
        token = login.json()["token"]

        fake_messages = [{"version": "v0.9", "createSurface": {"surfaceId": "confirmacion", "catalogId": "x"}}]
        app.state.orchestrator.confirm_action = AsyncMock(return_value=fake_messages)

        response = client.post(
            "/api/confirm-action",
            json={"proposal_id": "prop-1"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json() == {"a2ui_messages": fake_messages}
        app.state.orchestrator.confirm_action.assert_awaited_once_with("ana", "prop-1")


def _login(client) -> str:
    login = client.post("/api/login", json={"username": "ana", "password": "pass123"})
    return login.json()["token"]


def _login_luis(client) -> str:
    login = client.post("/api/login", json={"username": "luis", "password": "pass456"})
    return login.json()["token"]


def test_get_cuenta(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.get("/api/cuenta", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        body = response.json()
        assert body["numero_cuenta"] == "001122"
        assert body["saldo"] == 500.00


def test_get_cuenta_sin_token_devuelve_401(app):
    with TestClient(app) as client:
        response = client.get("/api/cuenta")
        assert response.status_code == 401


def test_get_movimientos_vacio(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.get("/api/movimientos", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json() == []


def test_get_movimientos_respeta_limit(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.get("/api/movimientos?limit=3", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200


def test_get_movimientos_falla_del_mcp_devuelve_400(app):
    with TestClient(app) as client:
        token = _login(client)
        app.state.mcp_client.call = AsyncMock(side_effect=RuntimeError("mcp caído"))
        response = client.get("/api/movimientos", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 400


def test_list_contactos(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.get("/api/contactos", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert len(response.json()) == 2


def test_create_contacto(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.post(
            "/api/contactos",
            json={"nombre": "Sofía López", "alias": "Sofi", "cuenta_destino": "5566778899", "relacion": "amiga"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.json()["nombre"] == "Sofía López"


def test_update_contacto(app):
    with TestClient(app) as client:
        token = _login(client)
        contacto_id = client.get("/api/contactos", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
        response = client.patch(
            f"/api/contactos/{contacto_id}",
            json={"alias": "Nuevo alias"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["alias"] == "Nuevo alias"


def test_update_contacto_inexistente_devuelve_400(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.patch(
            "/api/contactos/999999",
            json={"alias": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400


def test_delete_contacto(app):
    with TestClient(app) as client:
        token = _login(client)
        contacto_id = client.get("/api/contactos", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
        response = client.delete(
            f"/api/contactos/{contacto_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 204


def test_list_ingresos_programados(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.get("/api/ingresos-programados", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert len(response.json()) == 1


def test_create_ingreso_programado(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.post(
            "/api/ingresos-programados",
            json={"descripcion": "Bono", "monto": 5000.0, "frecuencia": "anual", "proxima_fecha": "2026-12-01"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.json()["descripcion"] == "Bono"


def test_update_ingreso_programado_parcial(app):
    with TestClient(app) as client:
        token = _login(client)
        ingreso_id = client.get(
            "/api/ingresos-programados", headers={"Authorization": f"Bearer {token}"}
        ).json()[0]["id"]
        response = client.patch(
            f"/api/ingresos-programados/{ingreso_id}",
            json={"monto": 13000.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["monto"] == 13000.0
        assert response.json()["descripcion"] == "Nómina"


def test_delete_ingreso_programado(app):
    with TestClient(app) as client:
        token = _login(client)
        ingreso_id = client.get(
            "/api/ingresos-programados", headers={"Authorization": f"Bearer {token}"}
        ).json()[0]["id"]
        response = client.delete(
            f"/api/ingresos-programados/{ingreso_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 204


def test_list_gastos_fijos(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.get("/api/gastos-fijos", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert len(response.json()) == 4


def test_create_gasto_fijo(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.post(
            "/api/gastos-fijos",
            json={"concepto": "Internet", "monto": 600.0, "frecuencia": "mensual", "proxima_fecha": "2026-10-05"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.json()["concepto"] == "Internet"


def test_update_gasto_fijo_parcial(app):
    with TestClient(app) as client:
        token = _login(client)
        gasto_id = client.get("/api/gastos-fijos", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
        response = client.patch(
            f"/api/gastos-fijos/{gasto_id}",
            json={"monto": 350.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["monto"] == 350.0


def test_update_gasto_fijo_con_null_explicito_no_corrompe_el_campo(app):
    with TestClient(app) as client:
        token = _login(client)
        gasto_id = client.get("/api/gastos-fijos", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
        original = client.get("/api/gastos-fijos", headers={"Authorization": f"Bearer {token}"}).json()[0]
        response = client.patch(
            f"/api/gastos-fijos/{gasto_id}",
            json={"proxima_fecha": None},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["proxima_fecha"] == original["proxima_fecha"]


def test_delete_gasto_fijo(app):
    with TestClient(app) as client:
        token = _login(client)
        gasto_id = client.get("/api/gastos-fijos", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
        response = client.delete(f"/api/gastos-fijos/{gasto_id}", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 204


def test_list_metas(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.get("/api/metas", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert len(response.json()) == 1


def test_create_meta(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.post(
            "/api/metas",
            json={"descripcion": "Viaje", "monto_objetivo": 20000.0, "fecha_objetivo": "2027-01-01"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.json()["monto_ahorrado"] == 0


def test_update_meta_parcial(app):
    with TestClient(app) as client:
        token = _login(client)
        meta_id = client.get("/api/metas", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
        response = client.patch(
            f"/api/metas/{meta_id}",
            json={"monto_objetivo": 9000.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["monto_objetivo"] == 9000.0


def test_delete_meta_sin_apartados(app):
    with TestClient(app) as client:
        token = _login(client)
        crear = client.post(
            "/api/metas",
            json={"descripcion": "Borrable", "monto_objetivo": 1000.0, "fecha_objetivo": "2027-01-01"},
            headers={"Authorization": f"Bearer {token}"},
        )
        meta_id = crear.json()["id"]
        response = client.delete(f"/api/metas/{meta_id}", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 204


def test_delete_meta_con_apartado_activo_devuelve_400(app):
    with TestClient(app) as client:
        token = _login(client)
        meta_id = client.get("/api/metas", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
        client.post(
            "/api/apartados",
            json={"meta_id": meta_id, "monto_por_periodo": 50.0, "periodicidad": "semanal"},
            headers={"Authorization": f"Bearer {token}"},
        )
        response = client.delete(f"/api/metas/{meta_id}", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 400
        assert "apartados activos" in response.json()["detail"]


def test_list_apartados_vacio(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.get("/api/apartados", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json() == []


def test_create_apartado(app):
    with TestClient(app) as client:
        token = _login(client)
        meta_id = client.get("/api/metas", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
        response = client.post(
            "/api/apartados",
            json={"meta_id": meta_id, "monto_por_periodo": 50.0, "periodicidad": "semanal"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.json()["estado"] == "activo"


def test_cancelar_apartado(app):
    with TestClient(app) as client:
        token = _login(client)
        meta_id = client.get("/api/metas", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
        apartado = client.post(
            "/api/apartados",
            json={"meta_id": meta_id, "monto_por_periodo": 50.0, "periodicidad": "semanal"},
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        response = client.post(
            f"/api/apartados/{apartado['id']}/cancelar", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["estado"] == "cancelado"


def test_cancelar_apartado_inexistente_devuelve_400(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.post("/api/apartados/999999/cancelar", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 400


def test_get_sugerencias_genera_y_lista(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.get("/api/sugerencias", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert isinstance(response.json(), list)


def test_get_sugerencias_no_duplica_entre_llamadas(app):
    with TestClient(app) as client:
        token = _login(client)
        primera = client.get("/api/sugerencias", headers={"Authorization": f"Bearer {token}"}).json()
        segunda = client.get("/api/sugerencias", headers={"Authorization": f"Bearer {token}"}).json()
        assert len(segunda) == len(primera)


def test_atender_sugerencia(app):
    with TestClient(app) as client:
        token = _login(client)
        sugerencias = client.get("/api/sugerencias", headers={"Authorization": f"Bearer {token}"}).json()
        sugerencia_id = sugerencias[0]["id"]
        response = client.post(
            f"/api/sugerencias/{sugerencia_id}/atender", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["estado"] == "atendida"


def test_descartar_sugerencia_inexistente_devuelve_400(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.post(
            "/api/sugerencias/999999/descartar", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 400


def test_get_score_salud_financiera(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.get("/api/score-salud-financiera", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        body = response.json()
        assert 0 <= body["score"] <= 100
        assert body["categoria"] in {"Saludable", "Atención", "Riesgo"}


def test_chat_sin_conversacion_id_crea_una_automaticamente(app):
    with TestClient(app) as client:
        token = _login(client)
        fake_messages = [{"version": "v0.9", "createSurface": {"surfaceId": "x", "catalogId": "y"}}]
        app.state.orchestrator.handle_message = AsyncMock(return_value=fake_messages)
        response = client.post(
            "/api/chat", json={"mensaje": "hola"}, headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        app.state.orchestrator.handle_message.assert_awaited_once()
        args = app.state.orchestrator.handle_message.await_args.args
        assert args[0] == "ana"
        assert isinstance(args[1], int)  # se autogeneró un conversacion_id real
        assert args[2] == "hola"


def test_chat_con_conversacion_id_lo_reenvia_tal_cual(app):
    with TestClient(app) as client:
        token = _login(client)
        fake_messages = [{"version": "v0.9", "createSurface": {"surfaceId": "x", "catalogId": "y"}}]
        app.state.orchestrator.handle_message = AsyncMock(return_value=fake_messages)
        creada = client.post(
            "/api/conversaciones", json={}, headers={"Authorization": f"Bearer {token}"}
        ).json()
        response = client.post(
            "/api/chat",
            json={"mensaje": "hola", "conversacion_id": creada["id"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        args = app.state.orchestrator.handle_message.await_args.args
        assert args[1] == creada["id"]


def test_crear_conversacion_titulo_por_defecto(app):
    with TestClient(app) as client:
        token = _login(client)
        response = client.post("/api/conversaciones", json={}, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 201
        assert response.json()["titulo"] == "Nueva conversación"


def test_listar_conversaciones(app):
    with TestClient(app) as client:
        token = _login(client)
        client.post("/api/conversaciones", json={"titulo": "Uno"}, headers={"Authorization": f"Bearer {token}"})
        response = client.get("/api/conversaciones", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert len(response.json()) == 1


def test_obtener_mensajes_de_conversacion(app):
    with TestClient(app) as client:
        token = _login(client)
        creada = client.post(
            "/api/conversaciones", json={}, headers={"Authorization": f"Bearer {token}"}
        ).json()
        response = client.get(
            f"/api/conversaciones/{creada['id']}/mensajes", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json() == []


def test_obtener_mensajes_de_conversacion_ajena_devuelve_400(app):
    with TestClient(app) as client:
        token_ana = _login(client)
        creada = client.post(
            "/api/conversaciones", json={}, headers={"Authorization": f"Bearer {token_ana}"}
        ).json()

        token_luis = _login_luis(client)
        response = client.get(
            f"/api/conversaciones/{creada['id']}/mensajes",
            headers={"Authorization": f"Bearer {token_luis}"},
        )
        assert response.status_code == 400


def test_eliminar_conversacion(app):
    with TestClient(app) as client:
        token = _login(client)
        creada = client.post(
            "/api/conversaciones", json={}, headers={"Authorization": f"Bearer {token}"}
        ).json()
        response = client.delete(
            f"/api/conversaciones/{creada['id']}", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 204
