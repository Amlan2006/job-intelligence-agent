from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProfileReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    source_id: str
    source_quote: str


class ContactCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    role: str
    company: str
    source_id: str
    source_quote: str
    profiles: list[ProfileReference]
    technical_skills: list[str]
    activity_date: str | None
    activity_source_id: str | None
    activity_quote: str | None


class ContactExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidates: list[ContactCandidate]


class ContactEvidence(BaseModel):
    source_url: str
    quote: str
    retrieved_at: datetime


class Contact(BaseModel):
    name: str
    role: str
    company: str
    linkedin_url: str | None = None
    x_url: str | None = None
    github_url: str | None = None
    association: Literal["officially_listed", "publicly_reported"]
    technical_skills: list[str]
    activity_date: date | None = None
    evidence: list[ContactEvidence]
    source_urls: list[str]
    relevance_score: float = Field(default=0, ge=0, le=100)
    score_components: dict[str, float] = Field(default_factory=dict)
    relevance_reason: str = ""
    warnings: list[str] = Field(default_factory=list)


class ContactDiscoveryRequest(BaseModel):
    resume_id: UUID | None = None


class ContactReport(BaseModel):
    company_id: UUID
    contacts: list[Contact]
    warnings: list[str]
