import re
from datetime import UTC, datetime

from app.services.skill_normalization import normalize_skill

WEIGHTS = {
    "role_relevance": 30,
    "authority": 25,
    "technical_overlap": 20,
    "company_association": 15,
    "recent_activity": 10,
}
ROLE_RULES = [
    (("cto", "chief technology officer", "chief technical officer"), 1.0, 1.0),
    (("vp engineering", "vp of engineering", "head of engineering", "head of protocol"), 1.0, 0.95),
    (("engineering manager",), 0.95, 0.8),
    (("staff engineer", "principal engineer"), 0.9, 0.6),
    (("protocol engineer",), 0.9, 0.4),
    (("founder",), 0.85, 1.0),
    (("technical recruiter", "engineering recruiter"), 0.8, 0.5),
    (("recruiter",), 0.6, 0.4),
    (("engineer",), 0.7, 0.3),
]


def rank_contacts(contacts, target_skills: list[str], limit: int = 10, today=None):
    today = today or datetime.now(UTC).date()
    target = {normalize_skill(skill).casefold() for skill in target_skills}
    ranked = []
    for contact in contacts:
        role = contact.role.casefold()
        relevance, authority = 0.0, 0.0
        for names, relevant, powerful in ROLE_RULES:
            if any(re.search(r"\b" + re.escape(name) + r"\b", role) for name in names):
                relevance, authority = relevant, powerful
                break
        overlap = target & {normalize_skill(skill).casefold() for skill in contact.technical_skills}
        activity = 0.0
        if contact.activity_date:
            age = (today - contact.activity_date).days
            activity = 1.0 if 0 <= age <= 30 else 0.5 if 30 < age <= 90 else 0.0
        components = {
            "role_relevance": relevance,
            "authority": authority,
            "technical_overlap": len(overlap) / len(target) if target else 0.0,
            "company_association": 1.0 if contact.association == "officially_listed" else 0.6,
            "recent_activity": activity,
        }
        score = round(sum(WEIGHTS[key] * value for key, value in components.items()), 2)
        reason = (
            f"Role: {contact.role}; association: {contact.association}; "
            f"documented skill overlap: {', '.join(sorted(overlap)) or 'none'}. "
            "Authority is a role-based heuristic; employment and activity need review."
        )
        ranked.append(
            contact.model_copy(
                update={
                    "relevance_score": score,
                    "score_components": components,
                    "relevance_reason": reason,
                }
            )
        )
    return sorted(ranked, key=lambda item: (-item.relevance_score, item.name.casefold()))[:limit]
