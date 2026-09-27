import asyncio
import ipaddress
import socket
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx

from app.schemas.evidence import Source


class FetchError(RuntimeError):
    pass


async def validate_public_url(url: str) -> None:
    parts = urlsplit(url)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.port not in {None, 80, 443}
    ):
        raise FetchError("Only public HTTP(S) URLs on standard ports are supported")
    try:
        async with asyncio.timeout(10):
            addresses = await asyncio.get_running_loop().getaddrinfo(
                parts.hostname,
                parts.port or (443 if parts.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
    except (OSError, TimeoutError) as exc:
        raise FetchError("Domain resolution failed") from exc
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise FetchError("Private or reserved network destinations are blocked")


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.links = [], []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        if tag == "a" and not self.hidden:
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


class WebpageFetcher:
    def __init__(self, client: httpx.AsyncClient, timeout: float = 15, max_bytes: int = 1_000_000):
        self.client, self.timeout, self.max_bytes = client, timeout, max_bytes

    async def fetch(self, url: str, source_id: str) -> tuple[Source, list[str]]:
        try:
            async with asyncio.timeout(self.timeout):
                return await self._fetch(url, source_id)
        except (httpx.HTTPError, TimeoutError, UnicodeError) as exc:
            raise FetchError("Webpage fetch failed") from exc

    async def _fetch(self, url: str, source_id: str) -> tuple[Source, list[str]]:
        for _ in range(4):
            await validate_public_url(url)
            async with self.client.stream(
                "GET",
                url,
                timeout=self.timeout,
                follow_redirects=False,
                headers={"User-Agent": "JobIntelligenceAgent/0.1"},
            ) as response:
                if response.is_redirect:
                    if "location" not in response.headers:
                        raise FetchError("Redirect without destination")
                    url = urljoin(url, response.headers["location"])
                    continue
                response.raise_for_status()
                if "text/html" not in response.headers.get("content-type", ""):
                    raise FetchError("Only HTML pages are supported")
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > self.max_bytes:
                        raise FetchError("Page exceeds size limit")
                parser = PageParser()
                parser.feed(content.decode(response.encoding or "utf-8", errors="replace"))
                text = " ".join(parser.parts)[:16000]
                if not text:
                    raise FetchError("No readable page text")
                source = Source(
                    id=source_id,
                    source_name=urlsplit(url).hostname or url,
                    source_url=url,
                    text=text,
                    retrieved_at=datetime.now(UTC),
                    kind="page",
                )
                links = [urljoin(url, href) for href in parser.links]
                return source, links
        raise FetchError("Too many redirects")
