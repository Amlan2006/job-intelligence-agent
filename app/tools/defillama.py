import asyncio
import hashlib
import json
import math
import re
from datetime import UTC, datetime
from urllib.parse import quote, urlsplit

import httpx

from app.schemas.discovery import FundingRound


class FundingSourceError(RuntimeError):
    pass


def name_key(value):
    return " ".join(value.casefold().split())


def public_shape(value):
    """Syntax check only; every fetched destination also gets DNS-based validation."""
    if not isinstance(value, str):
        return None
    try:
        parts = urlsplit(value)
        if (
            parts.scheme in {"http", "https"}
            and parts.hostname
            and not parts.username
            and not parts.password
            and parts.port in {None, 80, 443}
        ):
            return value
    except ValueError:
        pass
    return None


def normalize_raises(rows, protocols, source_url=None):
    from app.config import get_settings

    source_url = source_url or get_settings().defillama_raises_url
    if not isinstance(rows, list) or not isinstance(protocols, list):
        raise FundingSourceError("FUNDING_SOURCE_INVALID")
    by_id, by_name = {}, {}
    for item in protocols:
        if not isinstance(item, dict) or not public_shape(item.get("url")):
            continue
        if item.get("id") is not None:
            by_id.setdefault(str(item["id"]), set()).add(item["url"])
        if isinstance(item.get("name"), str):
            by_name.setdefault(name_key(item["name"]), set()).add(item["url"])
    rounds, warnings = {}, []
    for row in rows:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("name"), str)
            or not row["name"].strip()
        ):
            warnings.append("INVALID_FUNDING_ROW_SKIPPED")
            continue
        name = row["name"].strip()[:255]
        provider_id = str(row["defillamaId"]) if row.get("defillamaId") is not None else None
        notes = []
        announced = None
        try:
            timestamp = row.get("date")
            if timestamp is not None and not isinstance(timestamp, bool):
                announced = datetime.fromtimestamp(float(timestamp), UTC)
        except (ValueError, TypeError, OverflowError, OSError):
            notes.append("INVALID_FUNDING_DATE")
        amount = None
        try:
            raw = row.get("amount")
            if raw is not None and not isinstance(raw, bool):
                amount = float(raw) * 1_000_000  # /api/raises amounts are in USD millions.
                if not math.isfinite(amount) or amount < 0:
                    amount = None
                    notes.append("INVALID_FUNDING_AMOUNT")
        except (ValueError, TypeError, OverflowError):
            notes.append("INVALID_FUNDING_AMOUNT")
        round_type = row.get("round")
        round_type = round_type.strip() if isinstance(round_type, str) else None
        identity = [
            provider_id or name_key(name),
            announced.isoformat() if announced else None,
            name_key(round_type or ""),
            row.get("source") if not announced else None,
        ]
        key = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
        candidates = by_id.get(provider_id, set()) if provider_id else set()
        basis = "defillama_id"
        if not candidates and not provider_id:
            candidates = by_name.get(name_key(name), set())
            basis = "exact_registry_name"
        website = next(iter(candidates)) if len(candidates) == 1 else None
        if website is None:
            notes.append("COMPANY_WEBSITE_UNRESOLVED")
        investors = []
        for field in ("leadInvestors", "otherInvestors"):
            values = row.get(field)
            if isinstance(values, list):
                investors.extend(v.strip() for v in values if isinstance(v, str) and v.strip())
        normalized = FundingRound(
            funding_key=key,
            company_name=name,
            provider_id=provider_id,
            amount_usd=amount,
            round_type=round_type,
            announced_at=announced,
            investors=list(dict.fromkeys(investors)),
            category=row.get("category") if isinstance(row.get("category"), str) else None,
            source_url=public_shape(row.get("source")) or source_url,
            company_url=website,
            website_basis=basis if website else None,
            warnings=notes,
        )
        if key in rounds:
            previous = rounds[key]
            previous.investors = sorted(set(previous.investors + normalized.investors))
            if previous.amount_usd != amount:
                previous.amount_usd = None
                previous.warnings.append("CONFLICTING_FUNDING_AMOUNTS")
        else:
            rounds[key] = normalized
    return list(rounds.values()), sorted(set(warnings))


class DefiLlamaFunding:
    def __init__(self, client, api_key, timeout=30, *, settings=None):
        from app.config import get_settings

        self.settings = settings or get_settings()
        self.client, self.api_key, self.timeout = client, api_key, timeout

    async def _json(self, url):
        try:
            async with asyncio.timeout(self.timeout):
                async with self.client.stream(
                    "GET", url, follow_redirects=False, timeout=self.timeout
                ) as response:
                    response.raise_for_status()
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > 20_000_000:
                            raise FundingSourceError("FUNDING_SOURCE_TOO_LARGE")
                    return json.loads(data)
        except (httpx.HTTPError, ValueError, TimeoutError):
            # Provider URL contains a credential; never include request details in errors.
            raise FundingSourceError("FUNDING_SOURCE_UNAVAILABLE") from None

    async def fetch(self, **kwargs):
        if not self.api_key:
            raise FundingSourceError("DEFILLAMA_API_KEY_REQUIRED")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", self.api_key):
            raise FundingSourceError("DEFILLAMA_API_KEY_INVALID")
        data = await self._json(
            f"{self.settings.defillama_pro_base_url.rstrip('/')}/"
            f"{quote(self.api_key, safe='')}/api/raises"
        )
        if not isinstance(data, dict) or not isinstance(data.get("raises"), list):
            raise FundingSourceError("FUNDING_SOURCE_INVALID")
        warnings = []
        try:
            protocols = await self._json(self.settings.defillama_protocols_url)
            if not isinstance(protocols, list):
                raise FundingSourceError("PROTOCOL_REGISTRY_INVALID")
        except FundingSourceError:
            protocols = []
            warnings.append("PROTOCOL_REGISTRY_UNAVAILABLE")
        rounds, invalid = normalize_raises(
            data["raises"], protocols, self.settings.defillama_raises_url
        )
        return rounds, warnings + invalid
