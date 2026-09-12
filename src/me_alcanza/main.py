import logging
import os

import uvicorn
from dotenv import load_dotenv
from google import genai

from me_alcanza.backend.app import create_app

load_dotenv()

_logger = logging.getLogger(__name__)


def main():
    provider = os.environ.get("LLM_PROVIDER", "gemini")
    api_key = os.environ.get("GOOGLE_AI_STUDIO_API_KEY")
    if provider != "fake" and not api_key:
        _logger.warning(
            "GOOGLE_AI_STUDIO_API_KEY no está configurada — forzando LLM_PROVIDER=fake "
            "(modo offline) para que el backend arranque de todas formas."
        )
        provider = "fake"

    genai_client = genai.Client(api_key=api_key or "sin-configurar")
    app = create_app(
        genai_client=genai_client,
        model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
        jwt_secret=os.environ["JWT_SECRET"],
        db_path=os.environ.get("BANK_DB_PATH", "banco.db"),
        provider=provider,
    )
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    main()
