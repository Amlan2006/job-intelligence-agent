"""Live Codex/API/DB smoke using saved company/contact research and a saved resume."""

import argparse
import asyncio
import json
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.db.models import LLMRun, OutreachRecord
from app.db.repositories.company import CompanyRepository
from app.db.repositories.contact import ContactRepository
from app.db.repositories.opportunity import OpportunityRepository
from app.db.repositories.resume import ResumeRepository
from app.db.session import create_database
from app.main import create_app
from app.schemas.opportunity import OpportunityReport
from app.schemas.outreach import OutreachSelection


class LocalSelector:
    """No provider calls: only select the first supplied IDs for a persistence smoke."""

    async def invoke(self, messages, **kwargs):
        options = json.loads(messages[1].content)
        return OutreachSelection(
            company_evidence_id=options["company"][0]["id"],
            resume_evidence_id=options["resume"][0]["id"],
        )


async def seed(company_id, resume_id):
    engine, sessions = create_database(get_settings().database_url)
    try:
        company = await CompanyRepository(sessions).latest_report(company_id)
        contacts = await ContactRepository(sessions).latest(company_id)
        resume = await ResumeRepository(sessions).get(resume_id)
        assert company and contacts and contacts.contacts and resume
        report = OpportunityReport(
            opportunity_id=uuid4(),
            company=company,
            resume_id=resume_id,
            contacts=contacts.contacts,
            job=None,
            match=None,
            warnings=["SMOKE_TEST_SNAPSHOT: uses previously saved research; no fresh job analysis"],
        )
        await OpportunityRepository(sessions).save(report, uuid4(), [])
        return report.opportunity_id
    finally:
        await engine.dispose()


async def verify(report, local_only=False):
    engine, sessions = create_database(get_settings().database_url)
    try:
        async with sessions() as session:
            record = await session.get(OutreachRecord, UUID(report["outreach_id"]))
            assert record and record.report_json == report
            events = (
                await session.scalars(
                    select(LLMRun).where(LLMRun.research_run_id == record.research_run_id)
                )
            ).all()
            if not local_only:
                assert any(e.metadata_json["success"] for e in events)
            else:
                assert not events
            assert report["status"] == "draft" and len(report["drafts"]) == 4
            print("Verified four draft variants, saved snapshot and retrieval.")
            print(
                "Local selector only; no inference sent."
                if local_only
                else "Inference log verified."
            )
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("company_id", type=UUID)
    parser.add_argument("resume_id", type=UUID)
    parser.add_argument("--local-only", action="store_true", help="No external inference calls")
    args = parser.parse_args()
    opportunity_id = asyncio.run(seed(args.company_id, args.resume_id))
    with TestClient(create_app()) as client:
        if args.local_only:
            client.app.state.outreach_writer.llm = LocalSelector()
        response = client.post(
            "/api/v1/outreach/generate",
            json={
                "opportunity_id": str(opportunity_id),
                "contact_index": 0,
            },
        )
        assert response.status_code == 200, response.text
        report = response.json()
        retrieved = client.get(f"/api/v1/outreach/{report['outreach_id']}")
        assert retrieved.status_code == 200 and retrieved.json() == report
        print(
            {
                "contact": report["contact_name"],
                "outreach_id": report["outreach_id"],
                "channels": [d["channel"] for d in report["drafts"]],
            }
        )
    asyncio.run(verify(report, args.local_only))


if __name__ == "__main__":
    main()
