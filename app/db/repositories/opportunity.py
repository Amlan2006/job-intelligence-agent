from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.models import Job, LLMRun, Opportunity, OutreachRecord, ResearchRun, SkillEmbedding
from app.db.repositories.contact import save_snapshot
from app.schemas.contact import ContactReport
from app.schemas.opportunity import OpportunityReport


class OpportunityRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    async def save(self, report: OpportunityReport, run_id: UUID, events: list):
        async with self.sessions() as session, session.begin():
            session.add(ResearchRun(id=run_id, status="completed"))
            job_id = uuid4() if report.job else None
            if report.job:
                session.add(
                    Job(
                        id=job_id,
                        company_id=report.company.company_id,
                        profile_json=report.job.model_dump(mode="json"),
                    )
                )
            await session.flush()
            await save_snapshot(
                session,
                ContactReport(
                    company_id=report.company.company_id,
                    contacts=report.contacts,
                    warnings=report.warnings,
                ),
                run_id,
            )
            session.add(
                Opportunity(
                    id=report.opportunity_id,
                    company_id=report.company.company_id,
                    resume_id=report.resume_id,
                    job_id=job_id,
                    research_run_id=run_id,
                    report_json=report.model_dump(mode="json"),
                )
            )
            session.add_all(
                [
                    LLMRun(research_run_id=run_id, metadata_json=event.model_dump(mode="json"))
                    for event in events
                ]
            )
            if report.outreach:
                await session.flush()
                session.add(
                    OutreachRecord(
                        id=report.outreach.outreach_id,
                        opportunity_id=report.opportunity_id,
                        research_run_id=run_id,
                        report_json=report.outreach.model_dump(mode="json"),
                    )
                )

    async def get(self, opportunity_id: UUID):
        async with self.sessions() as session:
            row = await session.get(Opportunity, opportunity_id)
            return OpportunityReport.model_validate(row.report_json) if row else None

    async def list(self, limit: int):
        async with self.sessions() as session:
            rows = (
                await session.scalars(
                    select(Opportunity)
                    .order_by(Opportunity.created_at.desc(), Opportunity.id.desc())
                    .limit(limit)
                )
            ).all()
            return [OpportunityReport.model_validate(row.report_json) for row in rows]


class EmbeddingRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    async def get(self, texts: list[str], model: str):
        async with self.sessions() as session:
            rows = (
                await session.scalars(
                    select(SkillEmbedding).where(
                        SkillEmbedding.model == model, SkillEmbedding.text.in_(texts)
                    )
                )
            ).all()
            return {row.text: row.embedding.tolist() for row in rows}

    async def save(self, vectors: dict[str, list[float]], model: str):
        if not vectors:
            return
        async with self.sessions() as session, session.begin():
            await session.execute(
                insert(SkillEmbedding)
                .values(
                    [
                        {"text": text, "model": model, "embedding": vector}
                        for text, vector in vectors.items()
                    ]
                )
                .on_conflict_do_nothing()
            )
