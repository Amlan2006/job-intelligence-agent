from app.services.skill_normalization import normalize_skills, skill_in_quote


def test_aliases_duplicates_and_whitespace():
    assert normalize_skills([" Postgres ", "postgresql", "Golang", "go", "", "Python"]) == [
        "Go",
        "PostgreSQL",
        "Python",
    ]


def test_distinct_related_skills_stay_distinct():
    assert normalize_skills(["Ethereum", "EVM", "Solidity", "Foundry"]) == [
        "Ethereum",
        "EVM",
        "Foundry",
        "Solidity",
    ]


def test_quote_uses_alias_and_word_boundaries():
    assert skill_in_quote("PostgreSQL", "Built services using Postgres.")
    assert not skill_in_quote("Go", "Built Django services.")
