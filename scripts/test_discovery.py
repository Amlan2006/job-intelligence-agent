"""Local-only Phase 7 smoke: real API/graph/PostgreSQL with synthetic provider fixtures."""

import argparse
import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from app.agents.funding_discovery import FundingCandidate, FundingExtraction, TavilyFunding
from app.db.repositories.discovery import DiscoveryBusy
from app.graph.opportunity import build_opportunity_graph
from app.main import create_app
from app.schemas.discovery import DiscoveryReport
from app.tools.defillama import DefiLlamaFunding
from app.tools.web_search import TavilySearch
from app.tools.webpage import WebpageFetcher
from tests.opportunity_fixtures import job_profile
from tests.unit.agents.test_outreach_writer import inputs, writer


async def prepare(app):
    opportunity, resume = inputs()
    resume.filename = "synthetic-discovery-smoke.pdf"
    resume.warnings = ["SYNTHETIC_TEST_DATA"]
    company = opportunity.company
    company.company_id = await app.state.company_repository.company_id("example.com")
    company.warnings = ["SYNTHETIC_TEST_DATA"]
    async with app.state.sessions() as session, session.begin():
        await app.state.resume_repository.save(
            session,
            resume,
            hashlib.sha256(uuid4().bytes).hexdigest(),
            "Built Python APIs.",
            uuid4(),
            [],
        )
    company_graph, job, embeddings, cache, contacts, jobs = [AsyncMock() for _ in range(6)]
    company_graph.ainvoke.return_value = {"final_report": company}
    job.analyze.return_value = job_profile()
    embeddings.model = "synthetic-no-embeddings"
    embeddings.embed.return_value = {}
    cache.get.return_value = {}
    contacts.timeout = 1
    contacts.discover.return_value = (opportunity.contacts, [])
    jobs.find.return_value = "https://example.com/jobs/python"
    app.state.discovery_service.graph = build_opportunity_graph(
        company_graph,
        app.state.company_repository,
        job,
        embeddings,
        cache,
        0.88,
        contacts,
        writer(),
    )
    app.state.discovery_service.jobs = jobs
    abandoned = DiscoveryReport(
        discovery_id=uuid4(), resume_id=resume.resume_id, started_at=datetime.now(UTC)
    )
    await app.state.discovery_repository.save(abandoned)
    app.state.smoke_abandoned_id = abandoned.discovery_id
    # Two workers cannot process the same resume simultaneously.
    async with app.state.discovery_repository.lock(resume.resume_id):
        try:
            async with app.state.discovery_repository.lock(resume.resume_id):
                raise AssertionError("Concurrent discovery lock was incorrectly acquired")
        except DiscoveryBusy:
            pass
    return resume.resume_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["tavily", "defillama"], default="tavily")
    args = parser.parse_args()
    app = create_app()
    date = int((datetime.now(UTC) - timedelta(days=1)).timestamp())
    date_text = datetime.fromtimestamp(date, UTC).date().isoformat()
    event_quote = f"On {date_text}, Example Labs raised $2.5 million in a Seed round for DeFi."

    def fixture(request):
        if request.url.host == "api.tavily.com":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "url": "https://news.example/raise",
                            "title": "Funding",
                            "content": event_quote,
                        }
                    ]
                },
            )
        if request.url.host == "news.example":
            return httpx.Response(
                200,
                text=event_quote + '<a href="https://example.com/">Example Labs</a>',
                headers={"content-type": "text/html"},
            )
        if request.url.host == "pro-api.llama.fi":
            return httpx.Response(
                200,
                json={
                    "raises": [
                        {
                            "name": "Example Labs",
                            "date": date,
                            "amount": 2.5,
                            "round": "Seed",
                            "defillamaId": "fixture",
                            "category": "DeFi",
                            "source": "https://example.com",
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json=[
                {
                    "id": "fixture",
                    "name": "Example Labs",
                    "url": "https://example.com",
                }
            ],
        )

    with (
        TestClient(app) as client,
        patch("app.services.discovery.validate_public_url", AsyncMock()),
        patch("app.tools.webpage.validate_public_url", AsyncMock()),
    ):
        provider = httpx.AsyncClient(transport=httpx.MockTransport(fixture))
        try:
            llm = AsyncMock()
            llm.invoke.return_value = FundingExtraction(
                rounds=[
                    FundingCandidate(
                        company_name="Example Labs",
                        source_id="funding-0",
                        event_quote=event_quote,
                        announcement_date_text=date_text,
                        amount_text="$2.5 million",
                        round_type="Seed",
                        investors=[],
                        category="DeFi",
                        company_url="https://example.com/",
                    )
                ]
            )
            app.state.discovery_service.source = {
                "defillama": DefiLlamaFunding(provider, "synthetic-key"),
                "tavily": TavilyFunding(
                    TavilySearch(provider, "synthetic-key"), WebpageFetcher(provider), llm
                ),
            }
            resume_id = client.portal.call(prepare, app)
            payload = {"resume_id": str(resume_id), "source": args.source}
            response = client.post("/api/v1/discovery/run", json=payload)
            assert response.status_code == 200, response.text
            report = response.json()
            assert report["status"] == "completed" and len(report["results"]) == 1
            previous = client.get(f"/api/v1/discovery/runs/{app.state.smoke_abandoned_id}").json()
            assert previous["status"] == "partial" and previous["finished_at"]
            assert client.get(f"/api/v1/discovery/runs/{report['discovery_id']}").json() == report
            result = report["results"][0]
            opportunity = client.get(f"/api/v1/opportunities/{result['opportunity_id']}").json()
            assert opportunity["match"] and opportunity["contacts"] and opportunity["outreach"]
            assert opportunity["outreach"]["opportunity_id"] == opportunity["opportunity_id"]
            outreach = client.get(f"/api/v1/outreach/{opportunity['outreach']['outreach_id']}")
            assert outreach.status_code == 200 and outreach.json() == opportunity["outreach"]
            repeat = client.post("/api/v1/discovery/run", json=payload).json()
            assert repeat["skipped_cached"] == 1 and repeat["results"] == []
            print(
                "Verified normalization, full graph, ranking, storage, retrieval, "
                "locking and deduplication."
            )
            print("Synthetic provider fixtures only; no external inference, search or messages.")
            print(
                {
                    "discovery_id": report["discovery_id"],
                    "resume_id": str(resume_id),
                    "score": result["ranking"]["score"],
                }
            )
        finally:
            client.portal.call(provider.aclose)


if __name__ == "__main__":
    main()
