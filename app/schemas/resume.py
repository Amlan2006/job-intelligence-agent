from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SkillCategory = Literal[
    "languages",
    "frameworks",
    "blockchain_skills",
    "backend_skills",
    "frontend_skills",
    "infrastructure_skills",
    "databases",
]


class SkillEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    category: SkillCategory
    source_quote: str


class ResumeProject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str
    skills: list[str]
    source_quote: str


class Employment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company: str
    title: str
    start_date: str | None
    end_date: str | None
    description: str
    source_quote: str


class ResumeExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skills: list[SkillEvidence]
    projects: list[ResumeProject]
    open_source: list[ResumeProject]
    employment: list[Employment]
    years_experience: float | None = Field(ge=0, le=80)
    experience_quote: str | None


class ResumeProfile(BaseModel):
    skills: list[str]
    languages: list[str]
    frameworks: list[str]
    blockchain_skills: list[str]
    backend_skills: list[str]
    frontend_skills: list[str]
    infrastructure_skills: list[str]
    databases: list[str]
    skill_evidence: list[SkillEvidence]
    projects: list[ResumeProject]
    open_source: list[ResumeProject]
    employment: list[Employment]
    years_experience: float | None


class ResumeReport(BaseModel):
    resume_id: UUID
    filename: str
    page_count: int
    profile: ResumeProfile
    warnings: list[str]
    cached: bool = False
