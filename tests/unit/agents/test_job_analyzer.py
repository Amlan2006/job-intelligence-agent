from unittest.mock import AsyncMock

from app.agents.job_analyzer import JobAnalyzer
from app.schemas.job import JobExtraction, JobFact, Requirement
from tests.opportunity_fixtures import job_profile


async def test_grounded_job_extraction():
    source = job_profile().source
    source.text += " Backend Engineer at Example Labs. Remote within India. Minimum 3 years."
    fetcher, llm = AsyncMock(), AsyncMock()
    fetcher.fetch.return_value = (source, [])
    llm.invoke.return_value = JobExtraction(
        requirements=[
            Requirement(skill="Postgres", priority="preferred", source_quote=source.text),
            Requirement(skill="PostgreSQL", priority="required", source_quote=source.text),
            Requirement(skill="Kubernetes", priority="required", source_quote=source.text),
        ],
        facts=[
            JobFact(field=field, value=value, source_quote=source.text)
            for field, value in (
                ("title", "Backend Engineer"),
                ("company", "Example Labs"),
                ("remote", "true"),
                ("minimum_years_experience", "3"),
                ("location", "Remote within India"),
            )
        ],
    )
    job = await JobAnalyzer(fetcher, llm).analyze("https://example.com/jobs/1", "run")
    assert job.required_skills == ["PostgreSQL"] and not job.preferred_skills
    assert job.remote is True and job.minimum_years_experience == 3
    assert "UNSUPPORTED_REQUIREMENT_DROPPED" in job.warnings


async def test_unknown_and_unsupported_facts_stay_unknown():
    source = job_profile().source
    fetcher, llm = AsyncMock(), AsyncMock()
    fetcher.fetch.return_value = (source, [])
    llm.invoke.return_value = JobExtraction(
        requirements=[],
        facts=[
            JobFact(field="company", value="Invented", source_quote=source.text),
            JobFact(field="title", value="Backend Engineer", source_quote="Nonexistent quote"),
        ],
    )
    job = await JobAnalyzer(fetcher, llm).analyze("url", "run")
    assert job.company is None and job.title is None and job.remote is None
    assert "NO_EXPLICIT_SKILL_REQUIREMENTS" in job.warnings
