from unittest.mock import AsyncMock

import pytest

from app.agents.outreach_writer import OutreachUnavailable
from app.graph.opportunity import build_opportunity_graph
from tests.unit.agents.test_outreach_writer import inputs, writer


@pytest.mark.parametrize("failure", [False, True])
async def test_outreach_graph_preserves_opportunity_and_failure_is_partial(failure):
    opportunity, resume = inputs()
    company_graph, company_repo, job, embeddings, cache, finder = [AsyncMock() for _ in range(6)]
    company_graph.ainvoke.return_value = {"final_report": opportunity.company}
    finder.timeout = 1
    finder.discover.return_value = (opportunity.contacts, [])
    agent = writer()
    if failure:
        agent.generate = AsyncMock(
            side_effect=OutreachUnavailable("INSUFFICIENT_OUTREACH_EVIDENCE")
        )
    graph = build_opportunity_graph(
        company_graph, company_repo, job, embeddings, cache, 0.88, finder, agent
    )
    state = await graph.ainvoke(
        {
            "company_url": "https://example.com",
            "resume": resume,
            "research_run_id": "test",
            "warnings": [],
        }
    )
    report = state["final_report"]
    assert report.contacts and report.job is None
    if failure:
        assert report.outreach is None
        assert any(w.startswith("OUTREACH_UNAVAILABLE") for w in report.warnings)
    else:
        assert report.outreach.opportunity_id == report.opportunity_id
        assert len(report.outreach.drafts) == 4
