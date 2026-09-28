from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.agents.job_board_discovery import HiringCompany, HiringExtraction, JobBoardFunding
from app.schemas.discovery import FundingRound
from app.schemas.evidence import Source
from app.tools.defillama import FundingSourceError
from app.tools.webpage import FetchError


def setup():
    search, fetcher, llm, funding = [AsyncMock() for _ in range(4)]
    search.api_key = "test"
    quote = "Example Labs is hiring a Protocol Engineer. Apply now."
    source = Source(
        id="job-board-0",
        source_name="Job listing",
        source_url="https://board.example/jobs/engineer",
        text=quote,
        kind="page",
        retrieved_at=datetime.now(UTC),
        link_labels={"https://company.example/": "Example Labs"},
    )
    search.search.return_value = [source]

    async def fetch(url, source_id):
        if url == "https://company.example/":
            return source.model_copy(update={"id": source_id, "source_url": url}), []
        return source.model_copy(update={"id": source_id}), []

    fetcher.fetch.side_effect = fetch
    candidate = HiringCompany(
        company_name="Example Labs",
        source_id=source.id,
        job_title="Protocol Engineer",
        hiring_quote=quote,
        employer_quote="Example Labs",
        role_quote="Protocol Engineer",
        page_kind="listing",
        company_url="https://company.example/",
    )
    llm.invoke.return_value = HiringExtraction(companies=[candidate, candidate])
    funding.fetch.return_value = (
        [
            FundingRound(
                provider="tavily",
                funding_key="round",
                company_name="Example Labs",
                company_url="https://company.example/",
                source_url="https://news.example/raise",
                announced_at=datetime.now(UTC),
            )
        ],
        [],
    )
    agent = JobBoardFunding(search, fetcher, llm, funding, ["board.example"])
    return agent, source, candidate


async def test_jobs_seed_targeted_funding_and_preserve_listing():
    agent, source, _ = setup()
    rounds, warnings = await agent.fetch(lookback_days=30)
    assert len(rounds) == 1 and not warnings
    assert rounds[0].job_url == source.source_url
    assert rounds[0].evidence["hiring_quote"] == source.text
    agent.funding.fetch.assert_awaited_once()
    assert agent.funding.fetch.call_args.kwargs["company_name"] == "Example Labs"
    assert agent.funding.fetch.call_args.kwargs["lookback_days"] == 30


@pytest.mark.parametrize("change", ["invented_quote", "closed", "index", "invented_role"])
async def test_unsupported_employers_are_not_researched(change):
    agent, source, candidate = setup()
    if change == "invented_quote":
        candidate.hiring_quote = "Example Labs is hiring Protocol Engineer invented"
    elif change == "invented_role":
        candidate.role_quote = "Invented role"
    elif change == "closed":
        source.text += " Job closed."
    else:
        candidate.page_kind = "index"
    agent.llm.invoke.return_value = HiringExtraction(companies=[candidate])
    rounds, warnings = await agent.fetch()
    assert not rounds and any(w.startswith("JOB_") for w in warnings)
    agent.funding.fetch.assert_not_called()


async def test_same_name_different_company_domain_not_joined():
    agent, _, _ = setup()
    agent.funding.fetch.return_value[0][0].company_url = "https://other.example/"
    rounds, warnings = await agent.fetch()
    assert rounds[0].funding_status == "unverified"
    assert rounds[0].amount_usd is None
    assert "RECENT_FUNDING_NOT_VERIFIED: Example Labs" in warnings


async def test_no_funding_is_unknown_not_recently_funded():
    agent, _, _ = setup()
    agent.funding.fetch.return_value = [], []
    rounds, warnings = await agent.fetch()
    assert rounds[0].funding_status == "unverified"
    assert rounds[0].company_url == "https://company.example/"
    assert rounds[0].announced_at is None
    assert "RECENT_FUNDING_NOT_VERIFIED: Example Labs" in warnings


async def test_unreadable_listings_never_use_search_snippets():
    agent, _, _ = setup()
    agent.fetcher.fetch.side_effect = FetchError("blocked")
    rounds, warnings = await agent.fetch()
    assert not rounds and "NO_READABLE_JOB_LISTINGS" in warnings
    agent.llm.invoke.assert_not_called()


async def test_missing_key_and_out_of_scope_domains():
    agent, source, _ = setup()
    agent.search.api_key = ""
    with pytest.raises(FundingSourceError, match="TAVILY_API_KEY_REQUIRED"):
        await agent.fetch()
    agent.search.api_key = "test"
    source.source_url = "https://board.example.attacker.test/job"
    await agent.fetch()
    agent.fetcher.fetch.assert_not_called()


async def test_separate_quotes_and_generic_website_link_are_supported():
    agent, source, candidate = setup()
    source.text = "Example Labs. Protocol Engineer. Remote role. Apply now."
    source.link_labels = {"https://company.example/": "Company website"}
    candidate.hiring_quote = "Apply now."
    candidate.company_url = None
    agent.llm.invoke.return_value = HiringExtraction(companies=[candidate])
    rounds, _ = await agent.fetch()
    assert len(rounds) == 1


async def test_unresolved_website_does_not_block_funding_search():
    agent, source, candidate = setup()
    source.link_labels = {}
    candidate.company_url = "https://invented.example/"
    rounds, warnings = await agent.fetch()
    agent.funding.fetch.assert_awaited_once()
    assert not rounds and "EMPLOYER_WEBSITE_UNRESOLVED: Example Labs" in warnings
    assert not any(c.args[0] == candidate.company_url for c in agent.fetcher.fetch.call_args_list)


async def test_category_page_followed_to_job_listing():
    agent, source, candidate = setup()
    index = source.model_copy(update={"source_url": "https://board.example/web3", "text": "Jobs"})
    agent.search.search.return_value = [index]
    candidate.source_id = "job-board-1"
    agent.llm.invoke.return_value = HiringExtraction(companies=[candidate])

    async def fetch(url, source_id):
        if url == index.source_url:
            return index.model_copy(update={"id": source_id}), [source.source_url]
        return source.model_copy(update={"id": source_id, "source_url": url}), []

    agent.fetcher.fetch.side_effect = fetch
    rounds, _ = await agent.fetch()
    assert len(rounds) == 1 and rounds[0].job_url == source.source_url


async def test_search_website_requires_reciprocal_listing_link():
    agent, source, candidate = setup()
    source.link_labels = {}
    candidate.company_url = None
    home = source.model_copy(update={"source_url": "https://company.example/"})
    agent.search.search.side_effect = [[source], [home]]

    async def fetch(url, source_id):
        if url == home.source_url:
            return home, [source.source_url]
        return source, []

    agent.fetcher.fetch.side_effect = fetch
    rounds, _ = await agent.fetch()
    assert len(rounds) == 1


async def test_matching_name_without_reciprocal_link_is_not_a_verified_website():
    agent, source, candidate = setup()
    source.link_labels = {}
    candidate.company_url = None
    home = source.model_copy(update={"source_url": "https://company.example/"})
    agent.search.search.side_effect = [[source], [home]]
    rounds, warnings = await agent.fetch()
    assert not rounds
    assert "EMPLOYER_WEBSITE_UNRESOLVED: Example Labs" in warnings


async def test_separate_quote_cannot_come_from_another_page():
    agent, _, candidate = setup()
    candidate.employer_quote = "Example Labs builds a different product"
    rounds, warnings = await agent.fetch()
    assert not rounds and any(w.startswith("JOB_EMPLOYER_EVIDENCE_INVALID:") for w in warnings)
    agent.funding.fetch.assert_not_called()


@pytest.mark.parametrize("unreachable", [True, False])
async def test_observed_website_survives_failed_verification(unreachable):
    agent, source, _ = setup()

    async def fetch(url, source_id):
        if url == "https://company.example/":
            if unreachable:
                raise FetchError("403")
            return source.model_copy(update={"source_url": url, "text": "Welcome"}), []
        return source, []

    agent.fetcher.fetch.side_effect = fetch
    rounds, _ = await agent.fetch()
    assert len(rounds) == 1
    assert rounds[0].company_url == "https://company.example/"
    assert rounds[0].website_status == ("unreachable" if unreachable else "unverified")
    assert rounds[0].funding_status == "unverified"
    assert rounds[0].amount_usd is None
