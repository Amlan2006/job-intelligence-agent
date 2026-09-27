from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import select, text

from app.db.models import LLMRun, ResearchRun, Resume, ResumeProfileRecord
from app.schemas.resume import ResumeProfile, ResumeReport


class ResumeRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    @asynccontextmanager
    async def locked(self, content_hash: str):
        # Serialize duplicate uploads across processes; bound by the route's timeout.
        key = int.from_bytes(bytes.fromhex(content_hash[:16]), "big", signed=True)
        async with self.sessions() as session, session.begin():
            await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
            yield session

    async def get_by_hash(self, session, content_hash: str) -> ResumeReport | None:
        rows = (
            await session.execute(
                select(Resume, ResumeProfileRecord)
                .join(ResumeProfileRecord, ResumeProfileRecord.resume_id == Resume.id)
                .where(Resume.content_hash == content_hash)
            )
        ).first()
        return self._report(*rows) if rows else None

    async def save(
        self,
        session,
        report: ResumeReport,
        content_hash: str,
        extracted_text: str,
        run_id: UUID,
        events: list,
    ):
        session.add(
            Resume(
                id=report.resume_id,
                content_hash=content_hash,
                filename=report.filename,
                extracted_text=extracted_text,
                page_count=report.page_count,
            )
        )
        session.add(ResearchRun(id=run_id, status="completed"))
        await session.flush()
        session.add(
            ResumeProfileRecord(
                resume_id=report.resume_id,
                research_run_id=run_id,
                profile_json=report.profile.model_dump(mode="json"),
                warnings=report.warnings,
            )
        )
        session.add_all(
            [
                LLMRun(research_run_id=run_id, metadata_json=event.model_dump(mode="json"))
                for event in events
            ]
        )

    async def get(self, resume_id: UUID) -> ResumeReport | None:
        async with self.sessions() as session:
            rows = (
                await session.execute(
                    select(Resume, ResumeProfileRecord)
                    .join(ResumeProfileRecord, ResumeProfileRecord.resume_id == Resume.id)
                    .where(Resume.id == resume_id)
                )
            ).first()
            return self._report(*rows) if rows else None

    @staticmethod
    def _report(resume: Resume, profile: ResumeProfileRecord) -> ResumeReport:
        return ResumeReport(
            resume_id=resume.id,
            filename=resume.filename,
            page_count=resume.page_count,
            profile=ResumeProfile.model_validate(profile.profile_json),
            warnings=profile.warnings,
        )
