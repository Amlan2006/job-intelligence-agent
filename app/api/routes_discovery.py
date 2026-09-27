from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.db.repositories.discovery import DiscoveryBusy
from app.schemas.discovery import DiscoveryReport, DiscoveryRequest
from app.services.discovery import ResumeNotFound

router = APIRouter(prefix="/api/v1/discovery")


@router.post("/run", response_model=DiscoveryReport)
async def run(payload: DiscoveryRequest, request: Request):
    try:
        report = await request.app.state.discovery_service.run(payload)
        if report.status == "failed":
            return JSONResponse(status_code=503, content=report.model_dump(mode="json"))
        return report
    except ResumeNotFound as exc:
        raise HTTPException(404, detail={"code": "RESUME_NOT_FOUND"}) from exc
    except DiscoveryBusy as exc:
        raise HTTPException(409, detail={"code": "DISCOVERY_ALREADY_RUNNING"}) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503, detail={"code": "DATABASE_ERROR"}) from exc


@router.get("/runs", response_model=list[DiscoveryReport])
async def list_runs(
    request: Request, resume_id: UUID, limit: int = Query(default=20, ge=1, le=100)
):
    try:
        return await request.app.state.discovery_repository.list(resume_id, limit)
    except SQLAlchemyError as exc:
        raise HTTPException(503, detail={"code": "DATABASE_ERROR"}) from exc


@router.get("/runs/{discovery_id}", response_model=DiscoveryReport)
async def get_run(discovery_id: UUID, request: Request):
    try:
        report = await request.app.state.discovery_repository.get(discovery_id)
    except SQLAlchemyError as exc:
        raise HTTPException(503, detail={"code": "DATABASE_ERROR"}) from exc
    if report is None:
        raise HTTPException(404, detail={"code": "DISCOVERY_NOT_FOUND"})
    return report
