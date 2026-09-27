import math

from app.schemas.opportunity import MatchReport, SkillMatch
from app.services.skill_normalization import normalize_skill

WEIGHTS = {"required": 50, "preferred": 15, "projects": 15, "experience": 10, "open_source": 10}
# Directional partial credit; these relationships never prove an exact skill match.
RELATED = {
    "solidity": {"Foundry", "Hardhat"},
    "postgresql": {"pgx"},
    "go": {"go-chi"},
    "distributed systems": {"NATS"},
}


def cosine(a, b):
    if not a or len(a) != len(b) or not all(math.isfinite(x) for x in [*a, *b]):
        return 0.0
    denominator = math.sqrt(sum(x * x for x in a) * sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / denominator if denominator else 0.0


def match_requirement(requirement, skills, vectors, threshold):
    for skill in skills:
        if normalize_skill(skill).casefold() == normalize_skill(requirement.skill).casefold():
            kind = "exact" if skill.casefold() == requirement.skill.casefold() else "alias"
            return SkillMatch(
                requirement=requirement.skill,
                priority=requirement.priority,
                resume_skill=skill,
                kind=kind,
                credit=1,
                source_quote=requirement.source_quote,
                explanation="The resume lists this skill or its recognized alias.",
            )
    related = {name.casefold() for name in RELATED.get(requirement.skill.casefold(), set())}
    for skill in skills:
        if skill.casefold() in related:
            return SkillMatch(
                requirement=requirement.skill,
                priority=requirement.priority,
                resume_skill=skill,
                kind="related",
                credit=0.5,
                source_quote=requirement.source_quote,
                explanation="Related tooling provides partial evidence, not proficiency.",
            )
    if requirement.skill in vectors:
        candidates = [
            (cosine(vectors[requirement.skill], vectors[skill]), skill)
            for skill in skills
            if skill in vectors
        ]
        if candidates:
            similarity, skill = max(candidates)
            if similarity >= threshold:
                return SkillMatch(
                    requirement=requirement.skill,
                    priority=requirement.priority,
                    resume_skill=skill,
                    kind="semantic",
                    credit=0.5,
                    similarity=round(similarity, 4),
                    source_quote=requirement.source_quote,
                    explanation="Embedding similarity suggests overlap; review manually.",
                )
    return SkillMatch(
        requirement=requirement.skill,
        priority=requirement.priority,
        resume_skill=None,
        kind="missing",
        credit=0,
        source_quote=requirement.source_quote,
        explanation="No supporting skill was found in the stored resume profile.",
    )


def match_skills(resume, job, vectors=None, threshold=0.88):
    vectors = vectors or {}
    matches = [
        match_requirement(req, resume.skills, vectors, threshold) for req in job.requirements
    ]
    components, warnings, constraints = {}, [], []
    for priority in ("required", "preferred"):
        group = [match for match in matches if match.priority == priority]
        if group:
            components[priority] = sum(match.credit for match in group) / len(group)
    target = {normalize_skill(req.skill).casefold() for req in job.requirements}

    def relevance(items):
        if not items or not target:
            return 0.0
        covered = {normalize_skill(skill).casefold() for item in items for skill in item.skills}
        return len(target & covered) / len(target)

    if target:
        # Absence of a relevant project/contribution earns zero rather than being omitted.
        components["projects"] = relevance(resume.projects)
        components["open_source"] = relevance(resume.open_source)
    if job.minimum_years_experience is not None and job.minimum_years_experience > 0:
        years = resume.years_experience
        components["experience"] = (
            min(1.0, years / job.minimum_years_experience)
            if years is not None and job.minimum_years_experience > 0
            else 0.0
        )
        if years is None:
            warnings.append("EXPERIENCE_UNKNOWN: total experience was not explicitly stated")
        elif years < job.minimum_years_experience:
            constraints.append(
                f"Job requests {job.minimum_years_experience:g} years; resume states {years:g}."
            )
    if job.location:
        constraints.append(f"Job location/restrictions: {job.location}")
    if job.remote is False:
        constraints.append("This job explicitly requires on-site work.")
    elif job.remote is True:
        constraints.append("Remote work is stated; check any geographic restrictions.")
    constraints.append("Location and work authorization eligibility have not been verified.")
    denominator = sum(WEIGHTS[name] for name in components)
    effective = {name: WEIGHTS[name] / denominator for name in components} if denominator else {}
    score = (
        round(sum(components[name] * effective[name] for name in components) * 100, 2)
        if effective
        else None
    )
    if not matches:
        warnings.append("MATCH_UNAVAILABLE: no supported skill requirements")
        score = None
    if any(match.kind == "semantic" for match in matches):
        warnings.append("SEMANTIC_MATCHES_REQUIRE_REVIEW")
    relevant = [
        item.name
        for item in resume.projects
        if target & {normalize_skill(skill).casefold() for skill in item.skills}
    ]
    strong = [match for match in matches if match.credit == 1]
    partial = [match for match in matches if 0 < match.credit < 1]
    missing = [match for match in matches if match.credit == 0]
    talking_points = [
        f"Discuss your documented {match.resume_skill} experience for {match.requirement}."
        for match in strong
    ]
    talking_points += [f"Discuss the documented project: {name}." for name in relevant]
    return MatchReport(
        overall_score=score,
        components=components,
        effective_weights=effective,
        strong_matches=strong,
        partial_matches=partial,
        missing_requirements=missing,
        relevant_projects=relevant,
        talking_points=talking_points,
        constraints=constraints,
        warnings=warnings,
    )
