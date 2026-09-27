import asyncio
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy.exc import SQLAlchemyError

from app.llm.telemetry import inference_events
from app.schemas.opportunity import OpportunityReport, OpportunityRequest
from app.tools.webpage import FetchError, validate_public_url

router = APIRouter(prefix="/api/v1")


@router.post("/opportunity/analyze", response_model=OpportunityReport)
async def analyze_opportunity(payload: OpportunityRequest, request: Request):
    token = inference_events.set([])
    try:
        async with asyncio.timeout(request.app.state.settings.opportunity_timeout_seconds):
            resume = await request.app.state.resume_repository.get(payload.resume_id)
            if resume is None:
                raise HTTPException(404, detail={"code": "RESUME_NOT_FOUND"})
            for url in (payload.company_url, payload.job_url):
                if url:
                    await validate_public_url(str(url))
            run_id = uuid4()
            state = await request.app.state.opportunity_graph.ainvoke(
                {
                    "company_url": str(payload.company_url),
                    "job_url": str(payload.job_url) if payload.job_url else None,
                    "resume": resume,
                    "research_run_id": str(run_id),
                    "warnings": [],
                }
            )
            report = state["final_report"]
            events = [
                event
                for event in inference_events.get() or []
                if event.research_run_id == str(run_id)
            ]
            await request.app.state.opportunity_repository.save(report, run_id, events)
            return report
    except FetchError as exc:
        raise HTTPException(422, detail={"code": "INVALID_URL", "message": str(exc)}) from exc
    except TimeoutError as exc:
        raise HTTPException(504, detail={"code": "OPPORTUNITY_TIMEOUT"}) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503, detail={"code": "DATABASE_ERROR"}) from exc
    finally:
        inference_events.reset(token)


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityReport)
async def get_opportunity(opportunity_id: UUID, request: Request):
    try:
        report = await request.app.state.opportunity_repository.get(opportunity_id)
    except SQLAlchemyError as exc:
        raise HTTPException(503, detail={"code": "DATABASE_ERROR"}) from exc
    if report is None:
        raise HTTPException(404, detail={"code": "OPPORTUNITY_NOT_FOUND"})
    return report


@router.get("/opportunities", response_model=list[OpportunityReport])
async def list_opportunities(request: Request, limit: int = Query(default=20, ge=1, le=100)):
    try:
        return await request.app.state.opportunity_repository.list(limit)
    except SQLAlchemyError as exc:
        raise HTTPException(503, detail={"code": "DATABASE_ERROR"}) from exc
