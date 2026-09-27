import re


def name_key(name):
    return re.sub(r"\W+", " ", name.casefold()).strip()


def deduplicate_contacts(contacts):
    merged = []
    for contact in contacts:
        profiles = {url for url in (contact.linkedin_url, contact.x_url, contact.github_url) if url}
        existing = next(
            (
                item
                for item in merged
                if profiles
                & {url for url in (item.linkedin_url, item.x_url, item.github_url) if url}
                or (
                    name_key(item.name) == name_key(contact.name)
                    and item.company.casefold() == contact.company.casefold()
                )
            ),
            None,
        )
        if existing is None:
            merged.append(contact)
            continue
        # Prefer an official listing over an external snippet when roles disagree.
        primary = contact if contact.association == "officially_listed" else existing
        other = existing if primary is contact else contact
        conflict = any(
            getattr(primary, field)
            and getattr(other, field)
            and getattr(primary, field) != getattr(other, field)
            for field in ("linkedin_url", "x_url", "github_url")
        )
        warnings = existing.warnings + contact.warnings
        if conflict:
            # Do not conflate same-name people with conflicting accounts.
            warning = "IDENTITY_CONFLICT: same-name profiles require review"
            existing.warnings = list(dict.fromkeys(existing.warnings + [warning]))
            contact.warnings = list(dict.fromkeys(contact.warnings + [warning]))
            merged.append(contact)
            continue
        updated = primary.model_copy(
            update={
                **{
                    field: getattr(primary, field) or getattr(other, field)
                    for field in ("linkedin_url", "x_url", "github_url")
                },
                "technical_skills": sorted(
                    set(existing.technical_skills + contact.technical_skills)
                ),
                "source_urls": list(dict.fromkeys(existing.source_urls + contact.source_urls)),
                "evidence": existing.evidence + contact.evidence,
                "activity_date": max(
                    (date for date in (existing.activity_date, contact.activity_date) if date),
                    default=None,
                ),
                "warnings": list(dict.fromkeys(warnings)),
            }
        )
        merged[merged.index(existing)] = updated
    return merged
