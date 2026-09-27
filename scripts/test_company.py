"""Live company API, Codex, PostgreSQL and retrieval smoke check."""

import argparse
import asyncio
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import get_settings
from app.db.models import CompanyEvidence, LLMRun
from app.db.session import create_database
from app.main import create_app


async def verify_records(report):
    engine, sessions = create_database(get_settings().database_url)
    try:
        async with sessions() as session:
            run_id = UUID(report["research_id"])
            evidence_count = await session.scalar(
                select(func.count())
                .select_from(CompanyEvidence)
                .where(CompanyEvidence.research_run_id == run_id)
            )
            events = (
                await session.scalars(select(LLMRun).where(LLMRun.research_run_id == run_id))
            ).all()
            assert evidence_count == len(report["evidence"])
            assert events, "Inference telemetry was not persisted"
            print(f"Verified database evidence rows and {len(events)} inference event(s)")
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Public company website to research")
    args = parser.parse_args()
    with TestClient(create_app()) as client:
        assert client.get("/health/ready").status_code == 200
        response = client.post("/api/v1/research/company", json={"company_url": args.url})
        assert response.status_code == 200, response.text
        report = response.json()
        research = client.get(f"/api/v1/research/{report['research_id']}")
        assert research.status_code == 200 and research.json() == report
        company = client.get(f"/api/v1/company/{report['company_id']}")
        assert company.status_code == 200 and company.json() == report
        evidence = client.get(f"/api/v1/company/{report['company_id']}/evidence")
        assert evidence.status_code == 200 and evidence.json() == report["evidence"]
        print(
            {
                key: report[key]
                for key in (
                    "research_id",
                    "company_id",
                    "company_name",
                    "legitimacy_score",
                    "assessment",
                    "warnings",
                )
            }
        )
        print(f"Persisted and retrieved {len(report['evidence'])} evidence records")
    asyncio.run(verify_records(report))


if __name__ == "__main__":
    main()
