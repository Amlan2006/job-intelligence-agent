from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.agents.outreach_writer import OutreachUnavailable, OutreachWriter
from app.schemas.contact import ContactEvidence
from app.schemas.evidence import Evidence
from app.schemas.opportunity import OpportunityReport
from app.schemas.outreach import OutreachSelection
from app.schemas.resume import SkillEvidence
from tests.contact_fixtures import contact
from tests.opportunity_fixtures import company_report, resume_report


def inputs():
    resume = resume_report()
    resume.profile.skill_evidence = [
        SkillEvidence(name="Python", category="languages", source_quote="Built Python APIs.")
    ]
    company = company_report()
    company.evidence = [
        Evidence(
            evidence_type="product",
            source_name="Example Labs",
            source_url="https://example.com",
            claim="Developer tools",
            extracted_value="We build developer tools.",
            confidence=1,
            retrieved_at=datetime.now(UTC),
        )
    ]
    person = contact(
        evidence=[
            ContactEvidence(
                source_url="https://example.com/team",
                quote="Alice Smith is CTO at Example Labs.",
                retrieved_at=datetime.now(UTC),
            )
        ]
    )
    opportunity = OpportunityReport(
        opportunity_id=uuid4(),
        resume_id=resume.resume_id,
        company=company,
        job=None,
        match=None,
        contacts=[person],
        warnings=[],
    )
    return opportunity, resume


def writer():
    llm = AsyncMock()
    llm.invoke.return_value = OutreachSelection(
        company_evidence_id="company-0", resume_evidence_id="skill-0"
    )
    return OutreachWriter(llm)


async def test_grounded_four_variants():
    opportunity, resume = inputs()
    report = await writer().generate(opportunity, resume, 0, "run")
    assert report.status == "draft" and len(report.drafts) == 4
    assert len(report.drafts[0].body) <= 300
    for draft in report.drafts[1:]:
        assert "Built Python APIs." in draft.body
        assert "We build developer tools." in draft.body
        assert "3 years" not in draft.body
        assert set(draft.evidence_ids) <= {e.id for e in report.evidence}


@pytest.mark.parametrize("case", ["risk", "missing_contact", "conflict", "no_evidence", "resume"])
async def test_withholds_unsafe_inputs(case):
    opportunity, resume = inputs()
    if case == "risk":
        opportunity.company.assessment = "High-risk signals detected"
    elif case == "missing_contact":
        opportunity.contacts = []
    elif case == "conflict":
        opportunity.contacts[0].warnings = ["IDENTITY_CONFLICT: same-name profiles require review"]
    elif case == "no_evidence":
        opportunity.company.evidence = []
    else:
        resume.resume_id = uuid4()
    agent = writer()
    with pytest.raises(OutreachUnavailable):
        await agent.generate(opportunity, resume, 0, "run")
    agent.llm.invoke.assert_not_called()


async def test_fabricated_or_null_selection_rejected():
    opportunity, resume = inputs()
    agent = writer()
    for selected in ("invented", None):
        agent.llm.invoke.return_value = OutreachSelection(
            company_evidence_id=selected, resume_evidence_id="skill-0"
        )
        with pytest.raises(OutreachUnavailable):
            await agent.generate(opportunity, resume, 0, "run")
