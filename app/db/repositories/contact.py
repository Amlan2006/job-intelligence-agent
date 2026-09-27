import hashlib
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.models import CompanyPerson, ContactRun, LLMRun, Person, ResearchRun
from app.schemas.contact import ContactReport


async def save_snapshot(session, report: ContactReport, run_id):
    session.add(
        ContactRun(
            company_id=report.company_id,
            research_run_id=run_id,
            report_json=report.model_dump(mode="json"),
        )
    )
    for contact in report.contacts:
        profile = contact.linkedin_url or contact.x_url or contact.github_url
        identity = profile or f"{report.company_id}:{contact.name.casefold()}"
        key = hashlib.sha256(identity.encode()).hexdigest()
        await session.execute(
            insert(Person)
            .values(id=uuid4(), identity_key=key, name=contact.name[:255])
            .on_conflict_do_nothing(index_elements=[Person.identity_key])
        )
        person_id = await session.scalar(select(Person.id).where(Person.identity_key == key))
        await session.execute(
            insert(CompanyPerson)
            .values(
                company_id=report.company_id,
                person_id=person_id,
                contact_json=contact.model_dump(mode="json"),
            )
            .on_conflict_do_update(
                index_elements=[CompanyPerson.company_id, CompanyPerson.person_id],
                set_={"contact_json": contact.model_dump(mode="json")},
            )
        )


class ContactRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    async def save(self, report: ContactReport, run_id, events):
        async with self.sessions() as session, session.begin():
            session.add(ResearchRun(id=run_id, status="completed"))
            await session.flush()
            await save_snapshot(session, report, run_id)
            session.add_all(
                [
                    LLMRun(research_run_id=run_id, metadata_json=event.model_dump(mode="json"))
                    for event in events
                ]
            )

    async def latest(self, company_id):
        async with self.sessions() as session:
            payload = await session.scalar(
                select(ContactRun.report_json)
                .where(ContactRun.company_id == company_id)
                .order_by(ContactRun.created_at.desc(), ContactRun.id.desc())
                .limit(1)
            )
            return ContactReport.model_validate(payload) if payload else None
