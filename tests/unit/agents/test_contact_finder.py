from unittest.mock import AsyncMock

import pytest

from app.agents.contact_finder import ContactFinder, profile_url
from app.llm.router import LLMFailure
from app.schemas.contact import ContactExtraction, ProfileReference
from app.tools.web_search import SearchError
from app.tools.webpage import FetchError
from tests.contact_fixtures import candidate, source
from tests.opportunity_fixtures import company_report


@pytest.fixture
def finder():
    fetcher, search, llm = AsyncMock(), AsyncMock(), AsyncMock()
    fetcher.fetch.return_value = (source(), [])
    search.search.return_value = []
    llm.invoke.return_value = ContactExtraction(candidates=[candidate()])
    return ContactFinder(fetcher, search, llm)


async def test_official_contact_is_grounded_and_ranked(finder):
    contacts, warnings = await finder.discover(company_report(), ["Python"], "run")
    assert len(contacts) == 1 and contacts[0].relevance_score == 90
    assert contacts[0].association == "officially_listed"
    assert contacts[0].activity_date is None
    assert contacts[0].score_components["recent_activity"] == 0 and not warnings


async def test_fabricated_name_role_and_employer_dropped(finder):
    finder.llm.invoke.return_value = ContactExtraction(
        candidates=[
            candidate(name="Invented Name"),
            candidate(role="Founder"),
            candidate(company="Other Corp"),
        ]
    )
    contacts, warnings = await finder.discover(company_report(), [], "run")
    assert not contacts and "UNSUPPORTED_CONTACT_DROPPED" in warnings


async def test_profile_requires_own_source_and_matching_name(finder):
    external = source(
        id="search-0", source_url="https://www.linkedin.com/in/alice-smith", kind="search"
    )
    finder.search.search.return_value = [external]
    finder.llm.invoke.return_value.candidates[0].profiles = [
        ProfileReference(
            url=external.source_url,
            source_id="contact-search-0-search-0",
            source_quote=external.text,
        )
    ]
    contacts, _ = await finder.discover(company_report(), [], "run")
    assert contacts[0].linkedin_url == "https://linkedin.com/in/alice-smith"


async def test_fabricated_profile_is_dropped(finder):
    finder.llm.invoke.return_value.candidates[0].profiles = [
        ProfileReference(
            url="https://linkedin.com/in/invented",
            source_id="contact-home",
            source_quote=source().text,
        )
    ]
    contacts, _ = await finder.discover(company_report(), [], "run")
    assert contacts[0].linkedin_url is None
    assert "UNSUPPORTED_PROFILE_URL_DROPPED" in contacts[0].warnings


async def test_unstated_skill_not_used_for_overlap(finder):
    finder.llm.invoke.return_value.candidates[0].technical_skills = ["Kubernetes"]
    contacts, _ = await finder.discover(company_report(), ["Kubernetes"], "run")
    assert (
        not contacts[0].technical_skills and contacts[0].score_components["technical_overlap"] == 0
    )


async def test_future_activity_not_counted(finder):
    quote = source().text + " Alice Smith posted on 2099-01-01."
    finder.fetcher.fetch.return_value = (source(text=quote), [])
    person = finder.llm.invoke.return_value.candidates[0]
    person.activity_date, person.activity_source_id, person.activity_quote = (
        "2099-01-01",
        "contact-home",
        quote,
    )
    contacts, _ = await finder.discover(company_report(), [], "run")
    assert contacts[0].activity_date is None


async def test_former_employee_dropped(finder):
    quote = "Alice Smith is former CTO at Example Labs."
    finder.fetcher.fetch.return_value = (source(text=quote), [])
    finder.llm.invoke.return_value.candidates[0].source_quote = quote
    contacts, warnings = await finder.discover(company_report(), [], "run")
    assert not contacts and "FORMER_EMPLOYEE_DROPPED" in warnings


async def test_provider_failure_returns_warning(finder):
    finder.llm.invoke.side_effect = LLMFailure([])
    contacts, warnings = await finder.discover(company_report(), [], "run")
    assert not contacts and "CONTACT_EXTRACTION_FAILED" in warnings


async def test_no_public_sources(finder):
    finder.fetcher.fetch.side_effect = FetchError("unavailable")
    finder.search.search.side_effect = SearchError("unavailable")
    contacts, warnings = await finder.discover(company_report(), [], "run")
    assert not contacts and "NO_CONTACT_EVIDENCE" in warnings
    finder.llm.invoke.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "https://linkedin.com/company/example",
        "https://linkedin.com.evil/in/alice",
        "https://x.com/home",
        "https://github.com/orgs/example",
        "file:///tmp/file",
    ],
)
def test_non_profile_urls_rejected(url):
    assert profile_url(url) is None


@pytest.mark.parametrize(
    "url, expected",
    [
        (
            "https://uk.linkedin.com/in/alice?trk=test",
            ("linkedin_url", "https://linkedin.com/in/alice"),
        ),
        ("https://mobile.twitter.com/alice", ("x_url", "https://x.com/alice")),
        ("https://linkedin.com.evil.test/in/alice", None),
        ("https://x.com/login", None),
    ],
)
def test_profile_variants(url, expected):
    assert profile_url(url) == expected


async def test_official_named_anchor_used_without_url_in_text(finder):
    finder.fetcher.fetch.return_value = (
        source(
            link_labels={
                "https://linkedin.com/in/alice": "Alice Smith",
                "https://x.com/alice": "Alice Smith on X",
                "https://x.com/bob": "Bob Smith",
            }
        ),
        [],
    )
    contacts, _ = await finder.discover(company_report(), [], "run")
    assert contacts[0].linkedin_url == "https://linkedin.com/in/alice"
    assert contacts[0].x_url == "https://x.com/alice"
    assert contacts[0].profile_status == {"linkedin": "found", "x": "found"}


async def test_person_specific_search_enriches_missing_profile(finder):
    async def search(query):
        if '"Alice Smith"' in query and "linkedin" in query:
            return [source(source_url="https://uk.linkedin.com/in/alice", kind="search")]
        return []

    finder.search.search.side_effect = search
    contacts, _ = await finder.discover(company_report(), [], "run")
    assert contacts[0].linkedin_url == "https://linkedin.com/in/alice"
    assert contacts[0].profile_status["x"] == "not_found"


async def test_same_name_wrong_employer_rejected(finder):
    async def search(query):
        if '"Alice Smith"' in query:
            return [
                source(
                    source_url="https://linkedin.com/in/alice",
                    text="Alice Smith is CTO at Other Company",
                    source_name="Alice Smith — Other Company",
                    kind="search",
                )
            ]
        return []

    finder.search.search.side_effect = search
    contacts, _ = await finder.discover(company_report(), [], "run")
    assert contacts[0].linkedin_url is None
    assert contacts[0].profile_status["linkedin"] == "rejected"


async def test_conflicting_named_accounts_are_ambiguous(finder):
    finder.fetcher.fetch.return_value = (
        source(
            link_labels={
                "https://x.com/alice1": "Alice Smith",
                "https://x.com/alice2": "Alice Smith",
            }
        ),
        [],
    )
    contacts, _ = await finder.discover(company_report(), [], "run")
    assert contacts[0].x_url is None
    assert contacts[0].profile_status["x"] == "ambiguous"
