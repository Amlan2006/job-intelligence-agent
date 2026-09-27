from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.models import Company, CompanyEvidence, LLMRun, ResearchRun
from app.schemas.company import CompanyReport


class CompanyRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    async def company_id(self, domain: str) -> UUID:
        async with self.sessions() as session, session.begin():
            await session.execute(
                insert(Company)
                .values(id=uuid4(), domain=domain)
                .on_conflict_do_nothing(index_elements=[Company.domain])
            )
            return await session.scalar(select(Company.id).where(Company.domain == domain))

    async def save(self, report: CompanyReport, events: list) -> None:
        async with self.sessions() as session, session.begin():
            session.add(
                ResearchRun(
                    id=report.research_id,
                    company_id=report.company_id,
                    status="completed",
                    report=report.model_dump(mode="json"),
                )
            )
            await session.flush()
            session.add_all(
                [
                    CompanyEvidence(
                        research_run_id=report.research_id,
                        evidence_json=item.model_dump(mode="json"),
                    )
                    for item in report.evidence
                ]
            )
            session.add_all(
                [
                    LLMRun(
                        research_run_id=report.research_id,
                        metadata_json=event.model_dump(mode="json"),
                    )
                    for event in events
                ]
            )

    async def get_report(self, research_id: UUID) -> CompanyReport | None:
        async with self.sessions() as session:
            payload = await session.scalar(
                select(ResearchRun.report).where(ResearchRun.id == research_id)
            )
            return CompanyReport.model_validate(payload) if payload else None

    async def latest_report(self, company_id: UUID) -> CompanyReport | None:
        async with self.sessions() as session:
            payload = await session.scalar(
                select(ResearchRun.report)
                .where(ResearchRun.company_id == company_id, ResearchRun.report.is_not(None))
                .order_by(ResearchRun.created_at.desc(), ResearchRun.id.desc())
                .limit(1)
            )
            return CompanyReport.model_validate(payload) if payload else None
