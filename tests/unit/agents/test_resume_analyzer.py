from unittest.mock import AsyncMock

import pytest

from app.agents.resume_analyzer import ResumeAnalyzer
from app.schemas.resume import Employment, ResumeExtraction, ResumeProject, SkillEvidence
from tests.resume_fixtures import RESUME_LINES


@pytest.fixture
def extracted_resume():
    quote = RESUME_LINES[1]
    return ResumeExtraction(
        skills=[
            SkillEvidence(name=name, category=category, source_quote=quote)
            for name, category in (
                ("Python", "languages"),
                ("Postgres", "databases"),
                ("PostgreSQL", "databases"),
                ("Golang", "languages"),
                ("Docker", "infrastructure_skills"),
            )
        ],
        projects=[
            ResumeProject(
                name="Ledger API",
                description="Python API",
                skills=["Python", "PostgreSQL", "Docker"],
                source_quote=RESUME_LINES[2],
            )
        ],
        open_source=[],
        employment=[
            Employment(
                company="Example Labs",
                title="Backend Engineer",
                start_date="Jan 2023",
                end_date="Dec 2025",
                description="Built API services",
                source_quote=RESUME_LINES[3],
            )
        ],
        years_experience=3,
        experience_quote=RESUME_LINES[4],
    )


async def test_grounding_normalization_and_deduplication(extracted_resume):
    llm = AsyncMock()
    llm.invoke.return_value = extracted_resume
    profile, warnings = await ResumeAnalyzer(llm).analyze("\n".join(RESUME_LINES), "run")
    assert profile.skills == ["Docker", "Go", "PostgreSQL", "Python"]
    assert profile.databases == ["PostgreSQL"]
    assert len(profile.skill_evidence) == 4
    assert profile.projects[0].skills == ["Docker", "PostgreSQL", "Python"]
    assert profile.years_experience == 3 and not warnings


async def test_unsupported_skills_projects_dates_and_years_dropped(extracted_resume):
    extracted_resume.skills.append(
        SkillEvidence(
            name="Kubernetes",
            category="infrastructure_skills",
            source_quote=RESUME_LINES[1],
        )
    )
    extracted_resume.projects.append(
        ResumeProject(
            name="Invented Project",
            description="Made up",
            skills=[],
            source_quote=RESUME_LINES[2],
        )
    )
    extracted_resume.employment[0].start_date = "2010"
    extracted_resume.years_experience = 10
    llm = AsyncMock()
    llm.invoke.return_value = extracted_resume
    profile, warnings = await ResumeAnalyzer(llm).analyze("\n".join(RESUME_LINES), "run")
    assert "Kubernetes" not in profile.skills
    assert len(profile.projects) == 1
    assert profile.employment[0].start_date is None and profile.years_experience is None
    assert set(warnings) == {
        "UNSUPPORTED_SKILL_DROPPED",
        "UNSUPPORTED_PROJECT_DROPPED",
        "UNSUPPORTED_DATE_DROPPED",
        "UNSUPPORTED_EXPERIENCE_DROPPED",
    }


async def test_missing_sections_are_valid():
    llm = AsyncMock()
    llm.invoke.return_value = ResumeExtraction(
        skills=[],
        projects=[],
        open_source=[],
        employment=[],
        years_experience=None,
        experience_quote=None,
    )
    profile, warnings = await ResumeAnalyzer(llm).analyze("Alex Sample", "run")
    assert not profile.skills and profile.years_experience is None
    assert any("SPARSE_PROFILE" in warning for warning in warnings)
