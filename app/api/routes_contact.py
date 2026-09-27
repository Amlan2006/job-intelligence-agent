import asyncio
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from app.llm.telemetry import inference_events
from app.schemas.contact import ContactDiscoveryRequest, ContactReport

router = APIRouter(prefix="/api/v1/company")


@router.post("/{company_id}/contacts/discover", response_model=ContactReport)
async def discover_contacts(company_id: UUID, payload: ContactDiscoveryRequest, request: Request):
    token = inference_events.set([])
    try:
        async with asyncio.timeout(request.app.state.settings.contact_timeout_seconds):
            company = await request.app.state.company_repository.latest_report(company_id)
            if company is None:
                raise HTTPException(404, detail={"code": "COMPANY_NOT_FOUND"})
            if company.assessment in {"High-risk signals detected", "Insufficient evidence"}:
                raise HTTPException(409, detail={"code": "CONTACT_DISCOVERY_WITHHELD"})
            skills = []
            if payload.resume_id:
                resume = await request.app.state.resume_repository.get(payload.resume_id)
                if resume is None:
                    raise HTTPException(404, detail={"code": "RESUME_NOT_FOUND"})
                skills = resume.profile.skills
            run_id = uuid4()
            contacts, warnings = await request.app.state.contact_finder.discover(
                company, skills, str(run_id)
            )
            report = ContactReport(company_id=company_id, contacts=contacts, warnings=warnings)
            await request.app.state.contact_repository.save(report, run_id, inference_events.get())
            return report
    except TimeoutError as exc:
        raise HTTPException(504, detail={"code": "CONTACT_DISCOVERY_TIMEOUT"}) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503, detail={"code": "DATABASE_ERROR"}) from exc
    finally:
        inference_events.reset(token)


@router.get("/{company_id}/contacts", response_model=ContactReport)
async def get_contacts(company_id: UUID, request: Request):
    try:
        report = await request.app.state.contact_repository.latest(company_id)
    except SQLAlchemyError as exc:
        raise HTTPException(503, detail={"code": "DATABASE_ERROR"}) from exc
    if report is None:
        raise HTTPException(404, detail={"code": "CONTACT_REPORT_NOT_FOUND"})
    return report
