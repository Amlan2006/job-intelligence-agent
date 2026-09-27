from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.agents.funding_discovery import (
    FundingCandidate,
    FundingExtraction,
    TavilyFunding,
    grounded_round,
)
from app.schemas.evidence import Source
from app.tools.defillama import FundingSourceError
from app.tools.web_search import SearchError
from app.tools.webpage import FetchError, PageParser

NOW = datetime(2026, 9, 27, tzinfo=UTC)
QUOTE = (
    "On September 20, 2026, Example Labs raised $5 million in a Seed round led by Fund A for DeFi."
)


def candidate(**updates):
    return FundingCandidate(
        **(
            {
                "company_name": "Example Labs",
                "source_id": "funding-0",
                "event_quote": QUOTE,
                "announcement_date_text": "September 20, 2026",
                "amount_text": "$5 million",
                "round_type": "Seed",
                "investors": ["Fund A"],
                "category": "DeFi",
                "company_url": "https://example.com/",
            }
            | updates
        )
    )


def source(**updates):
    return Source(
        **(
            {
                "id": "funding-0",
                "source_name": "News",
                "source_url": "https://news.example/raise",
                "text": QUOTE,
                "kind": "page",
                "retrieved_at": NOW,
                "link_labels": {"https://example.com/": "Example Labs"},
            }
            | updates
        )
    )


def test_quote_grounded_values_and_named_website():
    result = grounded_round(candidate(), source(), NOW, 90)
    assert result.amount_usd == 5_000_000 and result.company_url == "https://example.com/"
    assert result.provider == "tavily" and result.evidence["event_quote"] == QUOTE
    assert result.announced_at == datetime(2026, 9, 20, tzinfo=UTC)


@pytest.mark.parametrize(
    "updates",
    [
        {"event_quote": "Invented"},
        {"company_name": "Fabricated Co"},
        {"announcement_date_text": "September 27, 2026"},
        {"announcement_date_text": "yesterday"},
    ],
)
def test_unsupported_events_or_inferred_dates_dropped(updates):
    assert grounded_round(candidate(**updates), source(), NOW, 90) is None


def test_recent_article_cannot_make_old_round_recent():
    quote = QUOTE.replace("2026", "2020")
    result = grounded_round(
        candidate(event_quote=quote, announcement_date_text="September 20, 2020"),
        source(text="Published today. " + quote),
        NOW,
        90,
    )
    assert result is None


def test_unsupported_fields_are_unknown_not_invented():
    result = grounded_round(
        candidate(
            amount_text="$100 million",
            round_type="Series B",
            investors=["Fake Fund"],
            category="AI",
            company_url="https://fake.example/",
        ),
        source(),
        NOW,
        90,
    )
    assert result.amount_usd is None and result.round_type is None
    assert result.investors == [] and result.category is None and result.company_url is None


def test_website_must_have_company_named_anchor():
    result = grounded_round(
        candidate(), source(link_labels={"https://example.com/": "Fund A"}), NOW, 90
    )
    assert result.company_url is None
    parser = PageParser()
    parser.feed('<a href="https://example.com/"><b>Example</b> Labs</a>')
    assert parser.link_labels["https://example.com/"] == "Example Labs"


async def test_search_fetch_extract_dedup_and_date_filters():
    search, fetcher, llm = [AsyncMock() for _ in range(3)]
    search.api_key = "fixture"
    search.search.return_value = [source()]
    fetcher.fetch.return_value = (source(), [])
    llm.invoke.return_value = FundingExtraction(rounds=[candidate(), candidate()])
    rounds, _ = await TavilyFunding(search, fetcher, llm).fetch(lookback_days=365)
    assert len(rounds) == 1 and fetcher.fetch.await_count == 1
    assert search.search.await_count == 3
    assert "start_date" in search.search.call_args.kwargs


async def test_unreadable_pages_do_not_use_snippets():
    search, fetcher, llm = [AsyncMock() for _ in range(3)]
    search.api_key = "fixture"
    search.search.return_value = [source()]
    fetcher.fetch.side_effect = FetchError("blocked")
    rounds, warnings = await TavilyFunding(search, fetcher, llm).fetch()
    assert not rounds and "NO_READABLE_FUNDING_ANNOUNCEMENTS" in warnings
    llm.invoke.assert_not_called()


async def test_missing_key_and_search_failure():
    search, fetcher, llm = [AsyncMock() for _ in range(3)]
    search.api_key = ""
    with pytest.raises(FundingSourceError, match="TAVILY_API_KEY_REQUIRED"):
        await TavilyFunding(search, fetcher, llm).fetch()
    search.api_key = "fixture"
    search.search.side_effect = SearchError("private")
    with pytest.raises(FundingSourceError, match="FUNDING_SEARCH_UNAVAILABLE"):
        await TavilyFunding(search, fetcher, llm).fetch()
