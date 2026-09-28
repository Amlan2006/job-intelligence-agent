from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from app.config import get_settings
from app.schemas.evidence import Source


class SearchError(RuntimeError):
    pass


class SearchProvider(Protocol):
    async def search(self, query: str) -> list[Source]: ...


class TavilySearch:
    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        timeout: float = 15,
        *,
        url: str | None = None,
    ):
        self.client, self.api_key, self.timeout = client, api_key, timeout
        self.url = url or get_settings().tavily_search_url

    async def search(self, query: str, *, start_date=None, end_date=None) -> list[Source]:
        if not self.api_key:
            raise SearchError("Search provider is not configured")
        try:
            response = await self.client.post(
                self.url,
                json={
                    "query": query,
                    "max_results": 5,
                    "include_answer": False,
                    **({"start_date": start_date, "end_date": end_date} if start_date else {}),
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return [
                Source(
                    id=f"search-{index}",
                    source_name=item.get("title") or urlsplit(item["url"]).netloc,
                    source_url=item["url"],
                    text=item.get("content", "")[:8000],
                    retrieved_at=datetime.now(UTC),
                    kind="search",
                )
                for index, item in enumerate(response.json()["results"])
                if item.get("url", "").startswith(("https://", "http://")) and item.get("content")
            ]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise SearchError("Search failed") from exc
