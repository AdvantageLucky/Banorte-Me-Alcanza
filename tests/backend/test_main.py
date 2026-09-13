import os

from google import genai

from me_alcanza.backend.anthropic_compat_client import AnthropicCompatClient
from me_alcanza.backend.openai_compat_client import OpenAICompatClient
from me_alcanza.main import _api_key_env_var, _build_llm_client


def test_api_key_env_var_openai():
    assert _api_key_env_var("openai") == "OPENAI_API_KEY"


def test_api_key_env_var_anthropic():
    assert _api_key_env_var("anthropic") == "ANTHROPIC_API_KEY"


def test_api_key_env_var_gemini():
    assert _api_key_env_var("gemini") == "GOOGLE_AI_STUDIO_API_KEY"


def test_build_llm_client_openai_usa_openai_compat_client(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    client, model = _build_llm_client("openai")
    assert isinstance(client, OpenAICompatClient)
    assert model == "gpt-test"


def test_build_llm_client_openai_usa_default_model_si_no_esta_seteado(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    _client, model = _build_llm_client("openai")
    assert model == "gpt-4o-mini"


def test_build_llm_client_anthropic_usa_anthropic_compat_client(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-test")
    client, model = _build_llm_client("anthropic")
    assert isinstance(client, AnthropicCompatClient)
    assert model == "claude-test"


def test_build_llm_client_anthropic_usa_default_model_si_no_esta_seteado(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    _client, model = _build_llm_client("anthropic")
    assert model == "claude-opus-5"


def test_build_llm_client_gemini_usa_genai_client(monkeypatch):
    monkeypatch.setenv("GOOGLE_AI_STUDIO_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    client, model = _build_llm_client("gemini")
    assert isinstance(client, genai.Client)
    assert model == "gemini-test"
