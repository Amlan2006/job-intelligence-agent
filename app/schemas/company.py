from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.schemas.evidence import Evidence, ExtractedClaim


class CompanyResearchRequest(BaseModel):
    company_url: HttpUrl


class CompanyExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_name: str
    description: str
    identity_source_id: str
    identity_quote: str
    claims: list[ExtractedClaim]


class CompanyReport(BaseModel):
    research_id: UUID
    company_id: UUID
    company_domain: str
    company_name: str | None
    company_description: str | None
    legitimacy_score: float = Field(ge=0, le=100)
    assessment: str
    positive_signals: list[Evidence]
    risk_signals: list[Evidence]
    evidence: list[Evidence]
    funding_information: list[Evidence]
    sources: list[str]
    warnings: list[str]
