from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .mcp_client import BankMcpClient, connect_mcp
from .orchestrator import Orchestrator
from .routes import router


def create_app(genai_client, model: str, jwt_secret: str, db_path: str) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with connect_mcp(db_path) as session:
            app.state.mcp_client = BankMcpClient(session)
            app.state.orchestrator = Orchestrator(genai_client, model, app.state.mcp_client)
            app.state.jwt_secret = jwt_secret
            yield

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app
