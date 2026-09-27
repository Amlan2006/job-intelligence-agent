import re
from urllib.parse import urlsplit

from app.tools.webpage import FetchError

BOARDS = {"jobs.lever.co", "boards.greenhouse.io", "job-boards.greenhouse.io", "jobs.ashbyhq.com"}


class JobDiscovery:
    def __init__(self, fetcher):
        self.fetcher = fetcher

    async def find(self, company_url):
        """Follow observed links to individual job pages."""
        try:
            _, links = await self.fetcher.fetch(company_url, "discovery-home")
            host = urlsplit(company_url).hostname
            career = [
                u
                for u in links
                if (
                    urlsplit(u).hostname == host
                    and re.search(r"/(careers|jobs)(/|$)", urlsplit(u).path)
                )
                or urlsplit(u).hostname in BOARDS
            ]
            for url in career[:2]:
                if self.is_job(url):
                    return url
                _, children = await self.fetcher.fetch(url, "discovery-careers")
                for child in children:
                    child_host = urlsplit(child).hostname or ""
                    if (child_host == host or child_host in BOARDS) and self.is_job(child):
                        return child
        except (FetchError, ValueError):
            pass
        return None

    @staticmethod
    def is_job(url):
        path = urlsplit(url).path
        return bool(
            re.search(r"/(jobs|careers)/[^/]+/?$", path) or re.search(r"/[0-9a-f-]{20,}/?$", path)
        )
