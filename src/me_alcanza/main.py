import logging
import os

import uvicorn
from dotenv import load_dotenv
from google import genai
from openai import OpenAI

from me_alcanza.backend.app import create_app
from me_alcanza.backend.openai_compat_client import OpenAICompatClient

load_dotenv()

_logger = logging.getLogger(__name__)

_PROVIDERS_CON_LLM_REAL = ("gemini", "openai")


def _build_llm_client(provider: str) -> tuple[object, str]:
    """Construye el cliente LLM y el nombre de modelo para el provider
    elegido. `genai.Client`/`OpenAICompatClient` exponen la misma superficie
    mínima (`.models.generate_content(...)`) que `orchestrator.py` usa —
    ver ADR 0022 y `openai_compat_client.py`."""
    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        openai_client = OpenAI(api_key=api_key or "sin-configurar")
        return OpenAICompatClient(openai_client, model=model), model

    api_key = os.environ.get("GOOGLE_AI_STUDIO_API_KEY")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    return genai.Client(api_key=api_key or "sin-configurar"), model


def _api_key_env_var(provider: str) -> str:
    return "OPENAI_API_KEY" if provider == "openai" else "GOOGLE_AI_STUDIO_API_KEY"


def main():
    provider = os.environ.get("LLM_PROVIDER", "gemini").strip().lower()
    if provider not in (*_PROVIDERS_CON_LLM_REAL, "fake"):
        _logger.warning(
            "LLM_PROVIDER=%r no es un valor reconocido (usa 'gemini', 'openai' o 'fake') — "
            "usando 'gemini' por defecto.",
            provider,
        )
        provider = "gemini"

    if provider in _PROVIDERS_CON_LLM_REAL and not os.environ.get(_api_key_env_var(provider)):
        _logger.warning(
            "%s no está configurada — forzando LLM_PROVIDER=fake (modo offline) para que el "
            "backend arranque de todas formas.",
            _api_key_env_var(provider),
        )
        provider = "fake"

    if provider == "fake":
        llm_client, model = _build_llm_client("gemini")  # cliente placeholder, nunca se usa en modo fake
    else:
        llm_client, model = _build_llm_client(provider)

    app = create_app(
        genai_client=llm_client,
        model=model,
        jwt_secret=os.environ["JWT_SECRET"],
        db_path=os.environ.get("BANK_DB_PATH", "banco.db"),
        provider=provider,
    )
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    main()
