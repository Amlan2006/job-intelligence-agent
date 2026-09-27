from contextlib import asynccontextmanager
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from app.db.models import DiscoveryCheckpoint, DiscoveryRun, FundingRoundRecord
from app.schemas.discovery import DiscoveryReport


class DiscoveryBusy(RuntimeError):
    pass


class DiscoveryRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    @asynccontextmanager
    async def lock(self, resume_id):
        async with self.sessions() as session, session.begin():
            acquired = await session.scalar(
                text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": f"discovery:{resume_id}"},
            )
            if not acquired:
                raise DiscoveryBusy("DISCOVERY_ALREADY_RUNNING")
            yield

    async def save(self, report, rounds=()):
        async with self.sessions() as session, session.begin():
            payload = report.model_dump(mode="json")
            await session.execute(
                insert(DiscoveryRun)
                .values(
                    id=report.discovery_id,
                    resume_id=report.resume_id,
                    report_json=payload,
                )
                .on_conflict_do_update(
                    index_elements=[DiscoveryRun.id], set_={"report_json": payload}
                )
            )
            rows = [
                {"funding_key": f.funding_key, "report_json": f.model_dump(mode="json")}
                for f in rounds
            ]
            for offset in range(0, len(rows), 500):
                statement = insert(FundingRoundRecord).values(rows[offset : offset + 500])
                await session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[FundingRoundRecord.funding_key],
                        set_={"report_json": statement.excluded.report_json},
                    )
                )

    async def recover_interrupted(self, resume_id):
        # Caller holds the resume lock, so any previous running report is abandoned.
        async with self.sessions() as session, session.begin():
            rows = await session.scalars(
                select(DiscoveryRun).where(
                    DiscoveryRun.resume_id == resume_id,
                    DiscoveryRun.report_json["status"].astext == "running",
                )
            )
            for row in rows:
                report = DiscoveryReport.model_validate(row.report_json)
                report.status = "partial"
                report.finished_at = datetime.now(UTC)
                report.warnings.append("DISCOVERY_INTERRUPTED: previous worker stopped")
                row.report_json = report.model_dump(mode="json")

    async def seen(self, key):
        async with self.sessions() as session:
            return await session.get(DiscoveryCheckpoint, key) is not None

    async def get(self, run_id):
        async with self.sessions() as session:
            row = await session.get(DiscoveryRun, run_id)
            return DiscoveryReport.model_validate(row.report_json) if row else None

    async def list(self, resume_id, limit):
        async with self.sessions() as session:
            rows = await session.scalars(
                select(DiscoveryRun)
                .where(DiscoveryRun.resume_id == resume_id)
                .order_by(DiscoveryRun.created_at.desc(), DiscoveryRun.id.desc())
                .limit(limit)
            )
            return [DiscoveryReport.model_validate(row.report_json) for row in rows]
