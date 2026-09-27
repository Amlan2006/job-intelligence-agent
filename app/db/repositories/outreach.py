from app.db.models import LLMRun, OutreachRecord, ResearchRun
from app.schemas.outreach import OutreachReport


class OutreachRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    async def save(self, report, run_id, events):
        async with self.sessions() as session, session.begin():
            session.add(ResearchRun(id=run_id, status="completed"))
            await session.flush()
            session.add(
                OutreachRecord(
                    id=report.outreach_id,
                    opportunity_id=report.opportunity_id,
                    research_run_id=run_id,
                    report_json=report.model_dump(mode="json"),
                )
            )
            session.add_all(
                [
                    LLMRun(research_run_id=run_id, metadata_json=e.model_dump(mode="json"))
                    for e in events
                ]
            )

    async def get(self, outreach_id):
        async with self.sessions() as session:
            row = await session.get(OutreachRecord, outreach_id)
            return OutreachReport.model_validate(row.report_json) if row else None
