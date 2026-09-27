"""Live resume upload, Codex extraction, persistence, and reuse smoke check."""

import argparse
import asyncio
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.db.models import LLMRun, Resume, ResumeProfileRecord
from app.db.session import create_database
from app.main import create_app


async def verify_database(resume_id: str):
    engine, sessions = create_database(get_settings().database_url)
    try:
        async with sessions() as session:
            resume = await session.get(Resume, UUID(resume_id))
            profile = await session.get(ResumeProfileRecord, UUID(resume_id))
            assert resume and resume.extracted_text and profile
            events = (
                await session.scalars(
                    select(LLMRun).where(LLMRun.research_run_id == profile.research_run_id)
                )
            ).all()
            assert events and any(event.metadata_json["success"] for event in events)
            print("Verified stored text, structured profile, and inference metadata")
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file", type=Path, help="Optional real PDF; defaults to a synthetic resume"
    )
    args = parser.parse_args()
    if args.file:
        content, filename = args.file.read_bytes(), args.file.name
    else:
        from tests.resume_fixtures import make_pdf

        content, filename = make_pdf(), "synthetic-resume.pdf"
    with TestClient(create_app()) as client:
        assert client.get("/health/ready").status_code == 200
        files = {"file": (filename, content, "application/pdf")}
        response = client.post("/api/v1/resume/analyze", files=files)
        assert response.status_code == 200, response.text
        report = response.json()
        retrieved = client.get(f"/api/v1/resume/{report['resume_id']}")
        assert retrieved.status_code == 200
        assert retrieved.json()["profile"] == report["profile"]
        repeated = client.post("/api/v1/resume/analyze", files=files)
        assert repeated.status_code == 200 and repeated.json()["cached"]
        assert repeated.json()["resume_id"] == report["resume_id"]
        print(
            {
                "resume_id": report["resume_id"],
                "skills": report["profile"]["skills"],
                "warnings": report["warnings"],
                "cached_reupload": repeated.json()["cached"],
            }
        )
    asyncio.run(verify_database(report["resume_id"]))


if __name__ == "__main__":
    main()
