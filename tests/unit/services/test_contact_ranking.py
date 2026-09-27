from datetime import date

from app.services.contact_deduplication import deduplicate_contacts
from app.services.contact_ranking import rank_contacts
from tests.contact_fixtures import contact


def test_role_authority_overlap_and_recency_weights():
    result = rank_contacts(
        [contact(activity_date=date(2026, 9, 20))], ["Python"], today=date(2026, 9, 27)
    )
    assert result[0].relevance_score == 100


def test_stale_activity_and_uncertain_employment():
    result = rank_contacts(
        [contact(association="publicly_reported", activity_date=date(2020, 1, 1))],
        [],
        today=date(2026, 9, 27),
    )
    assert result[0].relevance_score == 64 and result[0].score_components["recent_activity"] == 0


def test_director_does_not_match_cto_substring():
    ranked = rank_contacts([contact(role="Director")], [])
    assert ranked[0].score_components["authority"] == 0


def test_limit_and_sorting():
    result = rank_contacts(
        [contact(name=f"Person {index}", role="Recruiter") for index in range(20)] + [contact()],
        [],
        limit=5,
    )
    assert len(result) == 5 and result[0].name == "Alice Smith"


def test_dedup_prefers_official_and_preserves_evidence():
    people = [contact(association="publicly_reported", role="Engineer"), contact()]
    result = deduplicate_contacts(people)
    assert len(result) == 1 and result[0].role == "CTO"


def test_conflicting_same_name_profiles_are_not_merged():
    result = deduplicate_contacts(
        [
            contact(linkedin_url="https://linkedin.com/in/alice-a"),
            contact(linkedin_url="https://linkedin.com/in/alice-b"),
        ]
    )
    assert len(result) == 2
    assert all(item.warnings for item in result)
