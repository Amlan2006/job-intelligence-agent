from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from app.schemas.discovery import FundingRound
from app.services.discovery import DiscoveryService
from tests.unit.agents.test_outreach_writer import inputs


class MemoryDiscoveryRepository:
    def __init__(self):
        self.saved = {}
        self.keys = set()

    @asynccontextmanager
    async def lock(self, resume_id):
        yield

    async def save(self, report, rounds=()):
        self.saved[report.discovery_id] = report.model_copy(deep=True)

    async def seen(self, key):
        return key in self.keys

    async def recover_interrupted(self, resume_id):
        pass

    async def get(self, run_id):
        return self.saved.get(run_id)

    async def list(self, resume_id, limit):
        return [r for r in self.saved.values() if r.resume_id == resume_id][:limit]


def funding(**updates):
    return FundingRound(
        **(
            {
                "funding_key": "f" * 64,
                "company_name": "Example Labs",
                "amount_usd": 2500000,
                "announced_at": datetime.now(UTC) - timedelta(days=1),
                "category": "DeFi",
                "company_url": "https://example.com",
                "source_url": "https://example.com/funding",
            }
            | updates
        )
    )


def service():
    opportunity, resume = inputs()
    source, resumes, opportunities, graph, jobs = [AsyncMock() for _ in range(5)]
    repository = MemoryDiscoveryRepository()
    source.fetch.return_value = ([funding()], [])
    resumes.get.return_value = resume
    graph.ainvoke.return_value = {"final_report": opportunity}
    jobs.find.return_value = None

    async def save(report, run_id, events, discovery_key=None):
        repository.keys.add(discovery_key)

    opportunities.save.side_effect = save
    return DiscoveryService(source, repository, resumes, opportunities, graph, jobs, 1), resume
