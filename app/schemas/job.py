from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.evidence import Source


class Requirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skill: str
    priority: Literal["required", "preferred"]
    source_quote: str


class JobFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal[
        "title",
        "company",
        "seniority",
        "location",
        "remote",
        "role_domain",
        "responsibility",
        "minimum_years_experience",
    ]
    value: str
    source_quote: str


class JobExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirements: list[Requirement]
    facts: list[JobFact]


class JobProfile(BaseModel):
    title: str | None
    company: str | None
    seniority: str | None
    location: str | None
    remote: bool | None
    role_domain: str | None
    minimum_years_experience: float | None
    responsibilities: list[str]
    required_skills: list[str]
    preferred_skills: list[str]
    requirements: list[Requirement]
    facts: list[JobFact]
    source: Source
    warnings: list[str]
