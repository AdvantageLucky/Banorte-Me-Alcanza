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
        app.state.orchestrator.handle_message.assert_awaited_once_with("ana", "¿me alcanza para el concierto?")


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
