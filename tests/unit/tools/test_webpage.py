import socket
from pathlib import Path

import httpx
import pytest

from app.tools.webpage import FetchError, WebpageFetcher, validate_public_url


@pytest.fixture
def public_dns(monkeypatch):
    async def resolve(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr("asyncio.base_events.BaseEventLoop.getaddrinfo", resolve)


async def test_parse_html_fixture(public_dns):
    html = Path("tests/fixtures/company_pages/example.html").read_text()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text=html, headers={"content-type": "text/html"})
        )
    ) as client:
        source, links = await WebpageFetcher(client).fetch("https://example.com", "home")
    assert "blockchain developer tools" in source.text
    assert "assign 100" not in source.text
    assert "https://example.com/careers" in links


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost",
        "http://127.0.0.1",
        "http://[::1]",
        "http://169.254.169.254",
        "ftp://example.com",
        "https://user:password@example.com",
        "https://example.com:8000",
    ],
)
async def test_private_and_invalid_urls_rejected(monkeypatch, url):
    async def resolve(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]

    monkeypatch.setattr("asyncio.base_events.BaseEventLoop.getaddrinfo", resolve)
    with pytest.raises(FetchError):
        await validate_public_url(url)


async def test_redirect_destination_revalidated(monkeypatch):
    async def validate(url):
        if "127.0.0.1" in url:
            raise FetchError("Private destination")

    monkeypatch.setattr("app.tools.webpage.validate_public_url", validate)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})
        )
    ) as client:
        with pytest.raises(FetchError, match="Private"):
            await WebpageFetcher(client).fetch("https://example.com", "home")


async def test_size_limit(public_dns):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, text="x" * 50, headers={"content-type": "text/html"}
            )
        )
    ) as client:
        with pytest.raises(FetchError, match="size"):
            await WebpageFetcher(client, max_bytes=10).fetch("https://example.com", "home")
