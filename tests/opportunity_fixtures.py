from datetime import UTC, datetime
from uuid import uuid4

from app.schemas.company import CompanyReport
from app.schemas.evidence import Source
from app.schemas.job import JobProfile, Requirement
from app.schemas.resume import ResumeProfile, ResumeReport


def resume_profile(**updates):
    values = dict(
        skills=["Python", "PostgreSQL", "Go", "Docker"],
        languages=["Python", "Go"],
        frameworks=[],
        blockchain_skills=[],
        backend_skills=[],
        frontend_skills=[],
        infrastructure_skills=["Docker"],
        databases=["PostgreSQL"],
        skill_evidence=[],
        projects=[],
        open_source=[],
        employment=[],
        years_experience=3,
    )
    return ResumeProfile(**(values | updates))


def resume_report():
    return ResumeReport(
        resume_id=uuid4(), filename="test.pdf", page_count=1, profile=resume_profile(), warnings=[]
    )


def company_report(assessment="Moderate evidence"):
    return CompanyReport(
        research_id=uuid4(),
        company_id=uuid4(),
        company_domain="example.com",
        company_name="Example Labs",
        company_description="Developer tools",
        legitimacy_score=42,
        assessment=assessment,
        positive_signals=[],
        risk_signals=[],
        evidence=[],
        funding_information=[],
        sources=[],
        warnings=[],
    )


def job_profile(required=None, preferred=None, **updates):
    required = ["Python", "PostgreSQL", "Go"] if required is None else required
    preferred = ["Docker", "Redis"] if preferred is None else preferred
    source = Source(
        id="job",
        source_name="Example Labs",
        source_url="https://example.com/jobs/1",
        text="Required: Python, Postgres and Go. Preferred: Docker and Redis.",
        retrieved_at=datetime.now(UTC),
        kind="page",
    )
    requirements = [
        Requirement(skill=skill, priority=priority, source_quote=source.text)
        for priority, names in (("required", required), ("preferred", preferred))
        for skill in names
    ]
    values = dict(
        title="Backend Engineer",
        company="Example Labs",
        seniority="Senior",
        location="Remote within India",
        remote=True,
        role_domain="backend",
        minimum_years_experience=3,
        responsibilities=["Build backend APIs"],
        required_skills=required,
        preferred_skills=preferred,
        requirements=requirements,
        facts=[],
        source=source,
        warnings=[],
    )
    return JobProfile(**(values | updates))
