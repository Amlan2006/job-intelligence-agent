from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.agents.company_research import CompanyResearchAgent
from app.agents.contact_finder import ContactFinder
from app.agents.job_analyzer import JobAnalyzer
from app.agents.outreach_writer import OutreachWriter
from app.agents.resume_analyzer import ResumeAnalyzer
from app.api.routes_company import router as company_routes
from app.api.routes_contact import router as contact_routes
from app.api.routes_opportunity import router as opportunity_routes
from app.api.routes_outreach import router as outreach_routes
from app.api.routes_resume import router as resume_routes
from app.config import Settings, get_settings
from app.db.repositories.company import CompanyRepository
from app.db.repositories.contact import ContactRepository
from app.db.repositories.opportunity import EmbeddingRepository, OpportunityRepository
from app.db.repositories.outreach import OutreachRepository
from app.db.repositories.resume import ResumeRepository
from app.db.session import create_database
from app.graph.company import build_company_graph
from app.graph.graph import build_foundation_graph
from app.graph.opportunity import build_opportunity_graph
from app.llm.codex import CodexProvider
from app.llm.groq import GroqProvider
from app.llm.router import LLMRouter
from app.logging import configure_logging
from app.services.company_scoring import DEFAULT_WEIGHTS
from app.services.embeddings import LocalEmbeddings
from app.tools.resume_pdf import ResumePDFParser
from app.tools.web_search import TavilySearch
from app.tools.webpage import WebpageFetcher


class FoundationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        configure_logging(settings.log_level)
        engine, sessions = create_database(settings.database_url)
        application.state.engine, application.state.sessions = engine, sessions
        application.state.settings = settings
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
                application.state.llm_router = router
                application.state.company_graph = build_company_graph(
                    CompanyResearchAgent(
                        WebpageFetcher(client),
                        TavilySearch(client, settings.tavily_api_key.get_secret_value()),
                        router,
                    ),
                    DEFAULT_WEIGHTS | settings.company_score_weights,
                )
                application.state.company_repository = CompanyRepository(sessions)
                application.state.research_timeout = settings.research_timeout_seconds
                application.state.resume_repository = ResumeRepository(sessions)
                application.state.resume_parser = ResumePDFParser(settings)
                application.state.resume_analyzer = ResumeAnalyzer(router)
                application.state.opportunity_repository = OpportunityRepository(sessions)
                application.state.contact_repository = ContactRepository(sessions)
                application.state.outreach_repository = OutreachRepository(sessions)
                application.state.outreach_writer = OutreachWriter(
                    router, settings.outreach_timeout_seconds
                )
                application.state.contact_finder = ContactFinder(
                    WebpageFetcher(client),
                    TavilySearch(client, settings.tavily_api_key.get_secret_value()),
                    router,
                    settings.contact_limit,
                    settings.contact_timeout_seconds,
                )
                application.state.opportunity_graph = build_opportunity_graph(
                    application.state.company_graph,
                    application.state.company_repository,
                    JobAnalyzer(WebpageFetcher(client), router),
                    LocalEmbeddings(
                        settings.embedding_model,
                        settings.embedding_cache_dir,
                        settings.embedding_timeout_seconds,
                    ),
                    EmbeddingRepository(sessions),
                    settings.semantic_match_threshold,
                    application.state.contact_finder,
                    application.state.outreach_writer,
                )
                yield
        finally:
            await engine.dispose()

    application = FastAPI(title="Job Intelligence Agent", version="0.1.0", lifespan=lifespan)
    application.include_router(company_routes)
    application.include_router(resume_routes)
    application.include_router(opportunity_routes)
    application.include_router(contact_routes)
    application.include_router(outreach_routes)

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
