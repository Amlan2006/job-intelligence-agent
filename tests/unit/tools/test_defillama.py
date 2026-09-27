import logging
from datetime import UTC, datetime

import httpx
import pytest

from app.logging import JSONFormatter
from app.tools.defillama import DefiLlamaFunding, FundingSourceError, normalize_raises


def row(**updates):
    return {
        "name": "Example Labs",
        "date": 1750000000,
        "amount": 2.5,
        "round": "Seed",
        "defillamaId": "42",
        "category": "DeFi",
        "source": "https://news.example/raise",
        "leadInvestors": ["Fund A"],
        "otherInvestors": ["Fund A", "Fund B"],
        **updates,
    }


REGISTRY = [{"id": "42", "name": "Example Labs", "url": "https://example.com"}]


def test_normalization_units_dates_investors_and_dedup():
    rounds, warnings = normalize_raises([row(), row(name=" Example Labs ")], REGISTRY)
    assert len(rounds) == 1 and not warnings
    funding = rounds[0]
    assert funding.amount_usd == 2_500_000
    assert funding.announced_at == datetime.fromtimestamp(1750000000, UTC)
    assert funding.investors == ["Fund A", "Fund B"]
    assert funding.company_url == "https://example.com"
    assert funding.source_url == "https://news.example/raise"


@pytest.mark.parametrize("amount", [None, "undisclosed", -1, float("nan"), float("inf"), True])
def test_unknown_or_invalid_amount_never_becomes_zero(amount):
    rounds, _ = normalize_raises([row(amount=amount)], REGISTRY)
    assert rounds[0].amount_usd is None


def test_malformed_and_ambiguous_entities():
    rounds, warnings = normalize_raises(
        [None, {}, row(date="invalid", defillamaId=None)],
        REGISTRY + [{"name": "Example Labs", "url": "https://other.org"}],
    )
    assert len(rounds) == 1 and warnings
    assert rounds[0].announced_at is None and rounds[0].company_url is None


def test_conflicting_duplicate_amount_is_unknown_and_rounds_stay_distinct():
    rounds, _ = normalize_raises([row(), row(amount=3), row(date=1760000000)], REGISTRY)
    assert len(rounds) == 2 and rounds[0].amount_usd is None
    assert "CONFLICTING_FUNDING_AMOUNTS" in rounds[0].warnings


async def test_adapter_uses_documented_auth_and_public_registry():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(
            200, json={"raises": [row()]} if "/api/raises" in str(request.url) else REGISTRY
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        rounds, _ = await DefiLlamaFunding(client, "fixture-key").fetch()
    assert calls == [
        "https://pro-api.llama.fi/fixture-key/api/raises",
        "https://api.llama.fi/protocols",
    ]
    assert len(rounds) == 1


async def test_missing_key_does_not_call_provider():
    def handler(request):
        pytest.fail("unexpected provider call")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FundingSourceError, match="KEY_REQUIRED"):
            await DefiLlamaFunding(client, "").fetch()


@pytest.mark.parametrize("status,data", [(401, {}), (429, {}), (200, []), (200, {"raises": {}})])
async def test_errors_are_sanitized(status, data):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(status, json=data))
    ) as client:
        with pytest.raises(FundingSourceError) as error:
            await DefiLlamaFunding(client, "secret-fixture-key").fetch()
    assert "secret-fixture-key" not in str(error.value)


def test_key_redacted_in_application_logs():
    record = logging.LogRecord(
        "httpx",
        logging.INFO,
        "",
        0,
        "GET https://pro-api.llama.fi/secret-fixture-key/api/raises",
        (),
        None,
    )
    assert "secret-fixture-key" not in JSONFormatter().format(record)
