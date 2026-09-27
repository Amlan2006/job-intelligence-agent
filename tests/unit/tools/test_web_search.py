import json
from pathlib import Path

import httpx
import pytest

from app.tools.web_search import SearchError, TavilySearch


async def test_tavily_fixture():
    def respond(request):
        assert request.headers["authorization"] == "Bearer test-key"
        assert json.loads(request.content)["query"] == "Example Labs"
        return httpx.Response(
            200, json=json.loads(Path("tests/fixtures/search_results/company.json").read_text())
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        results = await TavilySearch(client, "test-key").search("Example Labs")
    assert len(results) == 1 and results[0].kind == "search"


async def test_missing_key():
    async with httpx.AsyncClient() as client:
        with pytest.raises(SearchError, match="not configured"):
            await TavilySearch(client, "").search("Example")


async def test_provider_error():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(429))
    ) as client:
        with pytest.raises(SearchError, match="Search failed"):
            await TavilySearch(client, "test-key").search("Example")
