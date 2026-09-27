import asyncio
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from app.agents.outreach_writer import OutreachUnavailable
from app.llm.router import LLMFailure
from app.llm.telemetry import inference_events
from app.schemas.outreach import OutreachReport, OutreachRequest

router = APIRouter(prefix="/api/v1/outreach")


@router.post("/generate", response_model=OutreachReport)
async def generate(payload: OutreachRequest, request: Request):
    token = inference_events.set([])
    try:
        async with asyncio.timeout(request.app.state.settings.outreach_timeout_seconds):
            opportunity = await request.app.state.opportunity_repository.get(payload.opportunity_id)
            if opportunity is None:
                raise HTTPException(404, detail={"code": "OPPORTUNITY_NOT_FOUND"})
            resume = await request.app.state.resume_repository.get(opportunity.resume_id)
            if resume is None:
                raise HTTPException(404, detail={"code": "RESUME_NOT_FOUND"})
            run_id = uuid4()
            report = await request.app.state.outreach_writer.generate(
                opportunity, resume, payload.contact_index, str(run_id)
            )
            await request.app.state.outreach_repository.save(
                report, run_id, inference_events.get() or []
            )
            return report
    except OutreachUnavailable as exc:
        raise HTTPException(409, detail={"code": str(exc)}) from exc
    except LLMFailure as exc:
        raise HTTPException(502, detail={"code": "OUTREACH_GENERATION_FAILED"}) from exc
    except TimeoutError as exc:
        raise HTTPException(504, detail={"code": "OUTREACH_TIMEOUT"}) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503, detail={"code": "DATABASE_ERROR"}) from exc
    finally:
        inference_events.reset(token)


@router.get("/{outreach_id}", response_model=OutreachReport)
async def get(outreach_id: UUID, request: Request):
    try:
        report = await request.app.state.outreach_repository.get(outreach_id)
    except SQLAlchemyError as exc:
        raise HTTPException(503, detail={"code": "DATABASE_ERROR"}) from exc
    if report is None:
        raise HTTPException(404, detail={"code": "OUTREACH_NOT_FOUND"})
    return report
