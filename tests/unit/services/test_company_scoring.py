from datetime import UTC, datetime

import pytest

from app.schemas.evidence import Evidence
from app.services.company_scoring import score_company


def evidence(signal):
    return Evidence(
        evidence_type=signal,
        source_name="fixture",
        source_url="https://example.com",
        claim=signal,
        confidence=0.7,
        retrieved_at=datetime.now(UTC),
    )


def test_positive_and_duplicate_signals():
    items = [evidence("website"), evidence("website"), evidence("product")]
    assert score_company(items)[0] == 20


def test_risk_reduces_score_and_overrides_assessment():
    items = [
        evidence("website"),
        evidence("product"),
        evidence("team"),
        evidence("identity_inconsistent"),
    ]
    score, assessment, _, risks = score_company(items)
    assert score == 10 and assessment == "High-risk signals detected"
    assert len(risks) == 1


@pytest.mark.parametrize("weights,expected", [({"website": 1000}, 100), ({"website": -1000}, 0)])
def test_bounds_and_configurable_weights(weights, expected):
    assert score_company([evidence("website")], weights)[0] == expected


def test_no_evidence():
    assert score_company([])[:2] == (0, "Insufficient evidence")
