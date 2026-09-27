from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.agents.company_research import CompanyResearchAgent
from app.llm.router import LLMFailure
from app.schemas.company import CompanyExtraction
from app.schemas.evidence import ExtractedClaim, Source
from app.tools.web_search import SearchError
from app.tools.webpage import FetchError


@pytest.fixture
def research_agent():
    home = Source(
        id="official-home",
        source_name="example.com",
        source_url="https://example.com/",
        text="Example Labs builds blockchain developer tools. "
        "Our product includes a public blockchain SDK.",
        retrieved_at=datetime.now(UTC),
        kind="page",
    )
    fetcher, search, llm = AsyncMock(), AsyncMock(), AsyncMock()
    fetcher.fetch.return_value = (home, [])
    search.search.return_value = []
    llm.invoke.return_value = CompanyExtraction(
        company_name="Example Labs",
        description="Blockchain developer tools",
        identity_source_id=home.id,
        identity_quote="Example Labs builds blockchain developer tools.",
        claims=[
            ExtractedClaim(
                signal="product",
                claim="Public SDK exists",
                source_id=home.id,
                quote="Our product includes a public blockchain SDK.",
            )
        ],
    )
    return CompanyResearchAgent(fetcher, search, llm)


async def test_grounded_claims(research_agent):
    research = await research_agent.research("https://example.com/", "run-id")
    assert research["company_name"] == "Example Labs"
    assert {item.evidence_type for item in research["evidence"]} == {
        "website",
        "https",
        "identity",
        "product",
    }


async def test_fabricated_quote_and_source_dropped(research_agent):
    extraction = research_agent.llm.invoke.return_value
    extraction.claims = [
        ExtractedClaim(
            signal="team",
            claim="100 engineers",
            source_id="official-home",
            quote="We employ one hundred engineers.",
        ),
        ExtractedClaim(
            signal="jobs", claim="Hiring", source_id="made-up", quote="We are hiring now."
        ),
    ]
    result = await research_agent.research("https://example.com", "run")
    assert "UNSUPPORTED_CLAIM_DROPPED" in result["warnings"]
    assert not any(item.evidence_type in {"team", "jobs"} for item in result["evidence"])


async def test_unconfirmed_funding_dropped(research_agent):
    source = research_agent.fetcher.fetch.return_value[0]
    source.text += " Example Labs raised six million dollars."
    research_agent.llm.invoke.return_value.claims = [
        ExtractedClaim(
            signal="funding_confirmed",
            claim="Raised $6M",
            source_id=source.id,
            quote="Example Labs raised six million dollars.",
        )
    ]
    result = await research_agent.research("https://example.com", "run")
    assert any("FUNDING_UNCONFIRMED" in warning for warning in result["warnings"])
    assert not any(item.evidence_type == "funding_confirmed" for item in result["evidence"])


async def test_llm_failure_returns_observations(research_agent):
    research_agent.llm.invoke.side_effect = LLMFailure([])
    result = await research_agent.research("https://example.com", "run")
    assert result["company_name"] is None
    assert len(result["evidence"]) == 2
    assert any("ALL_LLM_PROVIDERS_FAILED" in warning for warning in result["warnings"])


async def test_no_sources_returns_insufficient(research_agent):
    research_agent.fetcher.fetch.side_effect = FetchError("fixture failure")
    research_agent.search.search.side_effect = SearchError("fixture failure")
    result = await research_agent.research("https://example.com", "run")
    assert not result["evidence"]
    research_agent.llm.invoke.assert_not_called()
    assert any("INSUFFICIENT_EVIDENCE" in warning for warning in result["warnings"])


async def test_independently_corroborated_funding(research_agent):
    home = research_agent.fetcher.fetch.return_value[0]
    quote = "Example Labs raised six million dollars."
    home.text += " " + quote
    external = home.model_copy(
        update={
            "id": "investor",
            "kind": "search",
            "source_url": "https://investor.example/announcement",
        }
    )
    research_agent.search.search.return_value = [external]
    research_agent.llm.invoke.return_value.claims = [
        ExtractedClaim(
            signal="funding_confirmed",
            claim="Raised $6M",
            source_id=source.id,
            quote=quote,
        )
        for source in (home, external)
    ]
    result = await research_agent.research("https://example.com", "run")
    assert (
        len([item for item in result["evidence"] if item.evidence_type == "funding_confirmed"]) == 2
    )


async def test_unrelated_funding_claims_do_not_corroborate(research_agent):
    home = research_agent.fetcher.fetch.return_value[0]
    quote = "Example Labs raised six million dollars."
    home.text += " " + quote
    external = home.model_copy(
        update={
            "id": "investor",
            "kind": "search",
            "source_url": "https://investor.example/announcement",
        }
    )
    research_agent.search.search.return_value = [external]
    research_agent.llm.invoke.return_value.claims = [
        ExtractedClaim(
            signal="funding_confirmed", claim="Seed $6M", source_id=home.id, quote=quote
        ),
        ExtractedClaim(
            signal="funding_confirmed", claim="Series A $20M", source_id=external.id, quote=quote
        ),
    ]
    result = await research_agent.research("https://example.com", "run")
    assert not any(item.evidence_type == "funding_confirmed" for item in result["evidence"])


async def test_link_fetches_are_bounded_even_when_they_fail(research_agent):
    home = research_agent.fetcher.fetch.return_value[0]
    links = [f"https://example.com/about/{index}" for index in range(20)]
    research_agent.fetcher.fetch.side_effect = [(home, links)] + [FetchError("failure")] * 3
    await research_agent.research("https://example.com", "run")
    assert research_agent.fetcher.fetch.await_count == 4
