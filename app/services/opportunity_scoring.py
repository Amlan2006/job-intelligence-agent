from datetime import UTC, datetime

from app.schemas.discovery import OpportunityScore
from app.tools.defillama import name_key

WEIGHTS = {
    "resume_match": 30,
    "recent_funding": 20,
    "engineering_stack": 15,
    "open_positions": 15,
    "engineering_activity": 10,
    "growth": 10,
}


def score_opportunity(opportunity, funding, now=None):
    now = now or datetime.now(UTC)
    components = dict.fromkeys(WEIGHTS)
    warnings = ["HEURISTIC_SCORE: research priority, not hiring probability"]
    if opportunity.company.assessment in {"High-risk signals detected", "Insufficient evidence"}:
        return OpportunityScore(
            score=None,
            components=components,
            evidence_coverage=0,
            warnings=["RANKING_WITHHELD: company requires review"],
        )
    funding_associated = name_key(opportunity.company.company_name or "") == name_key(
        funding.company_name
    )
    if not funding_associated:
        warnings.append("FUNDING_COMPANY_NAME_UNVERIFIED: funding credit withheld")
    if funding.funding_status == "verified" and funding.announced_at and funding_associated:
        age = (now - funding.announced_at).total_seconds() / 86400
        if age >= 0:
            components["recent_funding"] = 1 if age <= 30 else 0.5 if age <= 90 else 0
    association_ok = not any(
        w.startswith("COMPANY_JOB_ASSOCIATION_UNVERIFIED") for w in opportunity.warnings
    )
    if opportunity.match and association_ok:
        if opportunity.match.overall_score is not None:
            components["resume_match"] = opportunity.match.overall_score / 100
        matches = (
            opportunity.match.strong_matches
            + opportunity.match.partial_matches
            + opportunity.match.missing_requirements
        )
        if matches:
            components["engineering_stack"] = sum(
                m.kind in {"exact", "alias"} for m in matches
            ) / len(matches)
    if opportunity.job and opportunity.job.requirements and association_ok:
        components["open_positions"] = 1
        warnings.append("JOB_AVAILABILITY_REQUIRES_REVIEW: a retrieved listing may be outdated")
    # A generic GitHub link or funding round cannot prove recent engineering activity/growth.
    missing = [key for key, value in components.items() if value is None]
    warnings.extend(f"UNKNOWN_{key.upper()}" for key in missing)
    coverage = sum(WEIGHTS[key] for key in components if components[key] is not None)
    total = sum(WEIGHTS[key] * value for key, value in components.items() if value is not None)
    return OpportunityScore(
        score=round(total, 2) if coverage else None,
        components=components,
        evidence_coverage=coverage,
        warnings=warnings,
    )
