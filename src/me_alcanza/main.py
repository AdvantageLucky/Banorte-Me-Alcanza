import os

import uvicorn
from dotenv import load_dotenv
from google import genai

from me_alcanza.backend.app import create_app

load_dotenv()


def main():
    genai_client = genai.Client(api_key=os.environ["GOOGLE_AI_STUDIO_API_KEY"])
    app = create_app(
        genai_client=genai_client,
        model=os.environ["GEMINI_MODEL"],
        jwt_secret=os.environ["JWT_SECRET"],
        db_path=os.environ.get("BANK_DB_PATH", "banco.db"),
    )
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
