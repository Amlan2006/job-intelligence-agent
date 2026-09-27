from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.schemas.company import CompanyReport
from app.schemas.contact import Contact
from app.schemas.job import JobProfile


class OpportunityRequest(BaseModel):
    company_url: HttpUrl
    job_url: HttpUrl | None = None
    resume_id: UUID


class SkillMatch(BaseModel):
    requirement: str
    priority: Literal["required", "preferred"]
    resume_skill: str | None
    kind: Literal["exact", "alias", "related", "semantic", "missing"]
    credit: float = Field(ge=0, le=1)
    similarity: float | None = None
    explanation: str
    source_quote: str


class MatchReport(BaseModel):
    overall_score: float | None = Field(default=None, ge=0, le=100)
    components: dict[str, float]
    effective_weights: dict[str, float]
    strong_matches: list[SkillMatch]
    partial_matches: list[SkillMatch]
    missing_requirements: list[SkillMatch]
    relevant_projects: list[str]
    talking_points: list[str]
    constraints: list[str]
    warnings: list[str]


class OpportunityReport(BaseModel):
    opportunity_id: UUID
    resume_id: UUID
    company: CompanyReport
    job: JobProfile | None
    match: MatchReport | None
    warnings: list[str]
    contacts: list[Contact] = Field(default_factory=list)
