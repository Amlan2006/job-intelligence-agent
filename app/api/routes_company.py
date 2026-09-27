import asyncio
import logging
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from app.llm.telemetry import inference_events
from app.schemas.company import CompanyReport, CompanyResearchRequest
from app.tools.webpage import FetchError, validate_public_url

router = APIRouter(prefix="/api/v1")
logger = logging.getLogger(__name__)


def repository(request: Request):
    return request.app.state.company_repository


@router.post("/research/company", response_model=CompanyReport)
async def research_company(payload: CompanyResearchRequest, request: Request):
    url = str(payload.company_url)
    try:
        await validate_public_url(url)
    except FetchError as exc:
        raise HTTPException(
            422, detail={"code": "INVALID_COMPANY_URL", "message": str(exc)}
        ) from exc
    run_id = str(uuid4())
    token = inference_events.set([])
    try:
        async with asyncio.timeout(request.app.state.research_timeout):
            company_id = await repository(request).company_id(urlsplit(url).hostname)
            state = await request.app.state.company_graph.ainvoke(
                {
                    "company_url": url,
                    "research_run_id": run_id,
                    "company_id": company_id,
                }
            )
            report = state["final_report"]
            await repository(request).save(report, inference_events.get())
            return report
    except TimeoutError as exc:
        raise HTTPException(504, detail={"code": "RESEARCH_TIMEOUT"}) from exc
    except SQLAlchemyError as exc:
        logger.error("database_failed", extra={"metadata": {"research_run_id": run_id}})
        raise HTTPException(503, detail={"code": "DATABASE_ERROR"}) from exc
    finally:
        inference_events.reset(token)


async def read_report(request: Request, identifier: UUID, latest: bool = False):
    try:
        report = (
            await repository(request).latest_report(identifier)
            if latest
            else await repository(request).get_report(identifier)
        )
    except SQLAlchemyError as exc:
        raise HTTPException(503, detail={"code": "DATABASE_ERROR"}) from exc
    if report is None:
        raise HTTPException(404, detail={"code": "REPORT_NOT_FOUND"})
    return report


@router.get("/research/{research_id}", response_model=CompanyReport)
async def get_research(research_id: UUID, request: Request):
    return await read_report(request, research_id)


@router.get("/company/{company_id}", response_model=CompanyReport)
async def get_company(company_id: UUID, request: Request):
    return await read_report(request, company_id, latest=True)


@router.get("/company/{company_id}/evidence")
async def get_evidence(company_id: UUID, request: Request):
    return (await read_report(request, company_id, latest=True)).evidence
