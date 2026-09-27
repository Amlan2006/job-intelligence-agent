from app.schemas.evidence import Evidence

DEFAULT_WEIGHTS = {
    "website": 10,
    "https": 2,
    "product": 10,
    "team": 10,
    "jobs": 10,
    "github_activity": 10,
    "funding_confirmed": 15,
    "investor_reference": 10,
    "social_presence": 5,
    "applicant_payment": -50,
    "identity_inconsistent": -20,
    "domain_imitation": -40,
}


def score_company(evidence: list[Evidence], weights: dict[str, int] | None = None):
    weights = DEFAULT_WEIGHTS if weights is None else weights
    # Each signal counts once, regardless of duplicate pages or claims.
    signals = {item.evidence_type for item in evidence}
    score = float(max(0, min(100, sum(weights.get(signal, 0) for signal in signals))))
    risks = [item for item in evidence if weights.get(item.evidence_type, 0) < 0]
    positives = [item for item in evidence if weights.get(item.evidence_type, 0) > 0]
    if signals & {"applicant_payment", "domain_imitation", "identity_inconsistent"}:
        assessment = "High-risk signals detected"
    elif score >= 60:
        assessment = "Strong evidence of being an operating company"
    elif score >= 30:
        assessment = "Moderate evidence"
    else:
        assessment = "Insufficient evidence"
    return score, assessment, positives, risks
