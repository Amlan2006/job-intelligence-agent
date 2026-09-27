from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Signal = Literal[
    "identity",
    "website",
    "https",
    "product",
    "team",
    "jobs",
    "github_activity",
    "funding_confirmed",
    "investor_reference",
    "social_presence",
    "applicant_payment",
    "identity_inconsistent",
    "domain_imitation",
]


class Source(BaseModel):
    id: str
    source_name: str
    source_url: str
    text: str
    retrieved_at: datetime
    kind: Literal["page", "search"]


class ExtractedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signal: Signal
    claim: str
    source_id: str
    quote: str


class Evidence(BaseModel):
    evidence_type: Signal
    source_name: str
    source_url: str
    claim: str
    extracted_value: str | None = None
    confidence: float = Field(ge=0, le=1)
    retrieved_at: datetime
