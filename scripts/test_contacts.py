"""Live Tavily/Codex contact discovery, persistence and retrieval smoke test."""

import argparse
import asyncio
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import get_settings
from app.db.models import CompanyPerson, ContactRun, LLMRun
from app.db.session import create_database
from app.main import create_app


async def verify_database(report):
    engine, sessions = create_database(get_settings().database_url)
    try:
        async with sessions() as session:
            company_id = UUID(report["company_id"])
            snapshot = await session.scalar(
                select(ContactRun)
                .where(ContactRun.company_id == company_id)
                .order_by(ContactRun.created_at.desc(), ContactRun.id.desc())
                .limit(1)
            )
            assert snapshot and snapshot.report_json == report
            count = await session.scalar(
                select(func.count())
                .select_from(CompanyPerson)
                .where(CompanyPerson.company_id == company_id)
            )
            events = (
                await session.scalars(
                    select(LLMRun).where(LLMRun.research_run_id == snapshot.research_run_id)
                )
            ).all()
            assert events and any(event.metadata_json["success"] for event in events)
            assert count >= len(report["contacts"])
            print(
                f"Verified contact snapshot, {count} company/person associations, and inference log"
            )
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("company_id", type=UUID)
    parser.add_argument("--resume-id", type=UUID)
    args = parser.parse_args()
    with TestClient(create_app()) as client:
        payload = {"resume_id": str(args.resume_id)} if args.resume_id else {}
        response = client.post(f"/api/v1/company/{args.company_id}/contacts/discover", json=payload)
        assert response.status_code == 200, response.text
        report = response.json()
        retrieved = client.get(f"/api/v1/company/{args.company_id}/contacts")
        assert retrieved.status_code == 200 and retrieved.json() == report
        print({"contacts_found": len(report["contacts"]), "warnings": report["warnings"]})
        for contact in report["contacts"]:
            print(
                contact["name"],
                contact["role"],
                contact["relevance_score"],
                contact["linkedin_url"] or contact["x_url"] or "No supported profile URL",
            )
    asyncio.run(verify_database(report))


if __name__ == "__main__":
    main()
