from datetime import UTC, datetime

from app.schemas.contact import Contact, ContactCandidate
from app.schemas.evidence import Source


def contact(**updates):
    values = dict(
        name="Alice Smith",
        role="CTO",
        company="Example Labs",
        association="officially_listed",
        technical_skills=["Python"],
        evidence=[],
        source_urls=["https://example.com/team"],
    )
    return Contact(**(values | updates))


def candidate(**updates):
    values = dict(
        name="Alice Smith",
        role="CTO",
        company="Example Labs",
        source_id="contact-home",
        source_quote="Alice Smith is CTO at Example Labs and builds Python services.",
        profiles=[],
        technical_skills=["Python"],
        activity_date=None,
        activity_source_id=None,
        activity_quote=None,
    )
    return ContactCandidate(**(values | updates))


def source(**updates):
    values = dict(
        id="contact-home",
        source_name="Example Labs",
        source_url="https://example.com/team",
        text="Alice Smith is CTO at Example Labs and builds Python services.",
        kind="page",
        retrieved_at=datetime.now(UTC),
    )
    return Source(**(values | updates))
