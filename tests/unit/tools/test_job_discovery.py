from unittest.mock import AsyncMock

from app.tools.job_discovery import JobDiscovery
from app.tools.webpage import FetchError


async def test_follows_official_careers_to_observed_job():
    fetcher = AsyncMock()
    fetcher.fetch.side_effect = [
        (None, ["https://example.com/careers"]),
        (None, ["https://example.com/jobs/python"]),
    ]
    assert (
        await JobDiscovery(fetcher).find("https://example.com") == "https://example.com/jobs/python"
    )


async def test_follows_observed_supported_external_board():
    fetcher = AsyncMock()
    job = "https://jobs.lever.co/example/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    fetcher.fetch.side_effect = [(None, ["https://jobs.lever.co/example"]), (None, [job])]
    assert await JobDiscovery(fetcher).find("https://example.com") == job


async def test_no_invented_job_from_unrelated_link_or_fetch_failure():
    fetcher = AsyncMock()
    fetcher.fetch.return_value = (None, ["https://unrelated.example/jobs/python"])
    assert await JobDiscovery(fetcher).find("https://example.com") is None
    fetcher.fetch.side_effect = FetchError("offline")
    assert await JobDiscovery(fetcher).find("https://example.com") is None
