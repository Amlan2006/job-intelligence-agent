"""Live Codex/embeddings/PostgreSQL smoke test with fixture pages or supplied URLs."""

import argparse
import asyncio
from pathlib import Path
from uuid import UUID

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.agents.company_research import CompanyResearchAgent
from app.agents.job_analyzer import JobAnalyzer
from app.config import Settings, get_settings
from app.db.models import Job, Opportunity
from app.db.repositories.opportunity import EmbeddingRepository
from app.db.session import create_database
from app.graph.company import build_company_graph
from app.graph.opportunity import build_opportunity_graph
from app.main import create_app
from app.services.company_scoring import DEFAULT_WEIGHTS
from app.services.embeddings import LocalEmbeddings
from app.tools.web_search import TavilySearch
from app.tools.webpage import WebpageFetcher


async def verify_database(report):
    engine, sessions = create_database(get_settings().database_url)
    try:
        async with sessions() as session:
            opportunity = await session.get(Opportunity, UUID(report["opportunity_id"]))
            assert opportunity and opportunity.job_id
            assert await session.get(Job, opportunity.job_id)
            count = await session.scalar(text("SELECT count(*) FROM skill_embeddings"))
            assert count > 0, "Local embeddings were not stored"
            distance = await session.scalar(
                text("SELECT embedding <=> embedding FROM skill_embeddings LIMIT 1")
            )
            assert abs(distance) < 0.00001
            print(f"Verified job, opportunity report, and {count} cached pgvector embeddings")
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--company-url")
    parser.add_argument("--job-url")
    parser.add_argument("--resume-id", type=UUID)
    args = parser.parse_args()
    if bool(args.company_url) != bool(args.job_url):
        parser.error("Supply both company and job URLs, or neither for fixture mode")
    settings = Settings(embedding_timeout_seconds=180)
    application = create_app(settings)
    fixture_client = None
    try:
        with TestClient(application) as client:
            company_url = args.company_url or "https://example.com"
            job_url = args.job_url or "https://example.com/jobs/backend"
            if not args.company_url:
                company_html = Path("tests/fixtures/company_pages/example.html").read_text()
                job_html = Path("tests/fixtures/jobs/backend_engineer.html").read_text()

                def respond(request):
                    html = (
                        job_html
                        if "career" in request.url.path or "jobs" in request.url.path
                        else company_html
                    )
                    return httpx.Response(200, text=html, headers={"content-type": "text/html"})

                fixture_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
                fetcher = WebpageFetcher(fixture_client)
                llm = application.state.llm_router
                company_graph = build_company_graph(
                    CompanyResearchAgent(
                        fetcher,
                        TavilySearch(fixture_client, ""),
                        llm,
                    ),
                    DEFAULT_WEIGHTS,
                )
                application.state.opportunity_graph = build_opportunity_graph(
                    company_graph,
                    application.state.company_repository,
                    JobAnalyzer(fetcher, llm),
                    LocalEmbeddings(
                        settings.embedding_model,
                        settings.embedding_cache_dir,
                        settings.embedding_timeout_seconds,
                    ),
                    EmbeddingRepository(application.state.sessions),
                    settings.semantic_match_threshold,
                )
            resume_id = args.resume_id
            if not resume_id:
                from tests.resume_fixtures import make_pdf

                resume = client.post(
                    "/api/v1/resume/analyze",
                    files={
                        "file": ("synthetic-resume.pdf", make_pdf(), "application/pdf"),
                    },
                )
                assert resume.status_code == 200, resume.text
                resume_id = resume.json()["resume_id"]
            response = client.post(
                "/api/v1/opportunity/analyze",
                json={
                    "company_url": company_url,
                    "job_url": job_url,
                    "resume_id": str(resume_id),
                },
            )
            assert response.status_code == 200, response.text
            report = response.json()
            assert (
                report["job"] and report["match"] and report["match"]["overall_score"] is not None
            )
            assert not any("EMBEDDINGS_UNAVAILABLE" in warning for warning in report["warnings"])
            retrieved = client.get(f"/api/v1/opportunities/{report['opportunity_id']}")
            assert retrieved.status_code == 200 and retrieved.json() == report
            listed = client.get("/api/v1/opportunities")
            assert any(item["opportunity_id"] == report["opportunity_id"] for item in listed.json())
            print(
                {
                    "opportunity_id": report["opportunity_id"],
                    "fixture_pages": not bool(args.company_url),
                    "score": report["match"]["overall_score"],
                    "warnings": report["warnings"],
                }
            )
        asyncio.run(verify_database(report))
    finally:
        if fixture_client is not None:
            asyncio.run(fixture_client.aclose())


if __name__ == "__main__":
    main()
