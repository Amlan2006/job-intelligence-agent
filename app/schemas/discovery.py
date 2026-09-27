from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class FundingRound(BaseModel):
    provider: str = "defillama"
    evidence: dict[str, str] = Field(default_factory=dict)
    funding_key: str
    company_name: str
    provider_id: str | None = None
    amount_usd: float | None = None
    round_type: str | None = None
    announced_at: datetime | None = None
    investors: list[str] = Field(default_factory=list)
    category: str | None = None
    source_url: str
    company_url: str | None = None
    website_basis: str | None = None
    warnings: list[str] = Field(default_factory=list)


class DiscoveryTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_url: HttpUrl
    job_url: HttpUrl | None = None


class DiscoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["tavily", "defillama"] = "tavily"
    resume_id: UUID
    lookback_days: int = Field(default=90, ge=1, le=365)
    limit: int = Field(default=3, ge=1, le=10)
    categories: list[str] = Field(default_factory=list, max_length=20)
    # Exact source company names; explicit mappings also cover unlisted protocol websites.
    targets: dict[str, DiscoveryTarget] = Field(default_factory=dict, max_length=50)
    force_refresh: bool = False


class OpportunityScore(BaseModel):
    score: float | None = Field(default=None, ge=0, le=100)
    components: dict[str, float | None]
    evidence_coverage: float = Field(ge=0, le=100)
    warnings: list[str]


class DiscoveryResult(BaseModel):
    funding: FundingRound
    status: Literal["analyzed", "unresolved", "failed"]
    opportunity_id: UUID | None = None
    ranking: OpportunityScore | None = None
    warnings: list[str] = Field(default_factory=list)


class DiscoveryReport(BaseModel):
    source: str = "defillama"
    source_inference: list[dict] = Field(default_factory=list)
    discovery_id: UUID
    resume_id: UUID
    started_at: datetime
    finished_at: datetime | None = None
    status: Literal["running", "completed", "partial", "failed"] = "running"
    results: list[DiscoveryResult] = Field(default_factory=list)
    skipped_cached: int = 0
    warnings: list[str] = Field(default_factory=list)
