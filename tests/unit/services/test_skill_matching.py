import pytest

from app.schemas.resume import ResumeProject
from app.services.skill_matching import cosine, match_skills
from tests.opportunity_fixtures import job_profile, resume_profile


def test_exact_alias_and_missing():
    job = job_profile(required=["Python", "Postgres", "Redis"], preferred=[])
    result = match_skills(resume_profile(), job)
    assert [item.kind for item in result.strong_matches] == ["exact", "alias"]
    assert result.missing_requirements[0].requirement == "Redis"
    assert result.components["required"] == pytest.approx(2 / 3)


def test_directional_related_tool_is_partial():
    result = match_skills(
        resume_profile(skills=["Foundry"]), job_profile(required=["Solidity"], preferred=[])
    )
    assert result.partial_matches[0].kind == "related"
    assert result.partial_matches[0].credit == 0.5


def test_semantic_similarity_gives_only_partial_credit():
    result = match_skills(
        resume_profile(skills=["Message queues"]),
        job_profile(required=["Messaging systems"], preferred=[]),
        {"Message queues": [1.0, 0.0], "Messaging systems": [1.0, 0.0]},
    )
    assert result.partial_matches[0].kind == "semantic"
    assert result.components["required"] == 0.5
    assert "SEMANTIC_MATCHES_REQUIRE_REVIEW" in result.warnings


def test_low_similarity_not_a_match():
    result = match_skills(
        resume_profile(skills=["Go"]),
        job_profile(required=["Java"], preferred=[]),
        {"Go": [1.0, 0.0], "Java": [0.0, 1.0]},
    )
    assert result.missing_requirements[0].requirement == "Java"


def test_project_evidence_experience_and_weights():
    project = ResumeProject(
        name="API", description="Backend API", skills=["Python"], source_quote="Python API"
    )
    result = match_skills(
        resume_profile(
            skills=["Python"], projects=[project], open_source=[project], years_experience=3
        ),
        job_profile(required=["Python"], preferred=[]),
    )
    assert result.overall_score == 100
    assert result.relevant_projects == ["API"]
    assert sum(result.effective_weights.values()) == pytest.approx(1)


def test_unknown_experience_does_not_invent_qualification():
    result = match_skills(resume_profile(years_experience=None), job_profile())
    assert result.components["experience"] == 0
    assert any("EXPERIENCE_UNKNOWN" in warning for warning in result.warnings)
    assert any("India" in constraint for constraint in result.constraints)


def test_empty_requirements_return_no_numeric_score():
    result = match_skills(resume_profile(), job_profile(required=[], preferred=[]))
    assert result.overall_score is None


@pytest.mark.parametrize("vectors", [([], []), ([1], [1, 0]), ([float("nan")], [1]), ([0], [0])])
def test_invalid_vectors_do_not_match(vectors):
    assert cosine(*vectors) == 0
