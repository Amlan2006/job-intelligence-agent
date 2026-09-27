from datetime import UTC, datetime, timedelta

from app.schemas.discovery import FundingRound
from app.services.opportunity_scoring import WEIGHTS, score_opportunity
from tests.unit.agents.test_outreach_writer import inputs


def test_unknowns_do_not_inflate_score():
    opportunity, _ = inputs()
    now = datetime.now(UTC)
    funding = FundingRound(
        funding_key="f",
        company_name="Example Labs",
        source_url="https://example.com",
        announced_at=now - timedelta(days=1),
    )
    result = score_opportunity(opportunity, funding, now)
    assert sum(WEIGHTS.values()) == 100
    assert result.score == 20 and result.evidence_coverage == 20
    assert result.components["resume_match"] is None
    opportunity.company.assessment = "High-risk signals detected"
    assert score_opportunity(opportunity, funding, now).score is None


def test_future_and_undated_rounds_earn_no_funding_points():
    opportunity, _ = inputs()
    for date in (None, datetime.now(UTC) + timedelta(days=1)):
        funding = FundingRound(
            funding_key="f",
            company_name="Example",
            source_url="https://example.com",
            announced_at=date,
        )
        assert score_opportunity(opportunity, funding).components["recent_funding"] is None
