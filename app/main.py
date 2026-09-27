from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.config import Settings, get_settings
from app.db.session import create_database
from app.graph.graph import build_foundation_graph
from app.llm.codex import CodexProvider
from app.llm.groq import GroqProvider
from app.llm.router import LLMRouter
from app.logging import configure_logging


class FoundationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        configure_logging(settings.log_level)
        engine, sessions = create_database(settings.database_url)
        application.state.engine, application.state.sessions = engine, sessions
        try:
            async with httpx.AsyncClient() as client:
                router = LLMRouter(
                    CodexProvider(
                        settings.codex_executable,
                        settings.codex_model,
                        settings.codex_timeout_seconds,
                    ),
                    GroqProvider(
                        client,
                        settings.groq_api_key.get_secret_value(),
                        settings.groq_model,
                        settings.groq_timeout_seconds,
                    ),
                    timeout=settings.codex_timeout_seconds,
                    fallback_timeout=settings.groq_timeout_seconds,
                )
                application.state.graph = build_foundation_graph(router)
                yield
        finally:
            await engine.dispose()

    application = FastAPI(title="Job Intelligence Agent", version="0.1.0", lifespan=lifespan)

    @application.get("/health")
    async def health():
        return {"status": "ok"}

    @application.get("/health/ready")
    async def readiness(request: Request):
        try:
            async with request.app.state.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return {"status": "ready"}

    @application.post("/api/v1/foundation/check")
    async def foundation_check(payload: FoundationRequest, request: Request):
        run_id = str(uuid4())
        state = await request.app.state.graph.ainvoke(
            {
                "research_run_id": run_id,
                "prompt": payload.prompt,
                "errors": [],
                "warnings": [],
            }
        )
        response = {
            "research_run_id": run_id,
            "result": state.get("result"),
            "errors": state.get("errors", []),
        }
        return JSONResponse(status_code=502 if response["errors"] else 200, content=response)

    return application


app = create_app()
