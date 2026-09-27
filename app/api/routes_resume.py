import asyncio
import hashlib
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from sqlalchemy.exc import SQLAlchemyError

from app.llm.router import LLMFailure
from app.llm.telemetry import inference_events
from app.schemas.resume import ResumeReport
from app.tools.resume_pdf import ResumeParseError

router = APIRouter(prefix="/api/v1/resume")


@router.post("/analyze", response_model=ResumeReport)
async def analyze_resume(request: Request, file: UploadFile = File(...)):
    settings = request.app.state.settings
    try:
        if file.content_type not in {None, "application/pdf", "application/octet-stream"}:
            raise HTTPException(415, detail={"code": "PDF_REQUIRED"})
        content = await file.read(settings.resume_max_bytes + 1)
    finally:
        await file.close()
    if not content:
        raise HTTPException(422, detail={"code": "EMPTY_FILE"})
    if len(content) > settings.resume_max_bytes:
        raise HTTPException(413, detail={"code": "PDF_SIZE_LIMIT"})
    if not content.startswith(b"%PDF-"):
        raise HTTPException(422, detail={"code": "INVALID_PDF"})
    filename = PurePosixPath((file.filename or "resume.pdf").replace("\\", "/")).name
    filename = "".join(char for char in filename if char.isprintable())[:255] or "resume.pdf"
    content_hash = hashlib.sha256(content).hexdigest()
    repo = request.app.state.resume_repository
    token = inference_events.set([])
    try:
        async with asyncio.timeout(settings.resume_analysis_timeout_seconds):
            async with repo.locked(content_hash) as session:
                cached = await repo.get_by_hash(session, content_hash)
                if cached:
                    return cached.model_copy(update={"cached": True})
                parsed = await request.app.state.resume_parser.parse(content)
                run_id = uuid4()
                profile, warnings = await request.app.state.resume_analyzer.analyze(
                    parsed["text"], str(run_id)
                )
                report = ResumeReport(
                    resume_id=uuid4(),
                    filename=filename,
                    page_count=parsed["page_count"],
                    profile=profile,
                    warnings=list(dict.fromkeys(parsed["warnings"] + warnings)),
                )
                await repo.save(
                    session, report, content_hash, parsed["text"], run_id, inference_events.get()
                )
            return report
    except ResumeParseError as exc:
        raise HTTPException(422, detail={"code": exc.code}) from exc
    except LLMFailure as exc:
        raise HTTPException(502, detail={"code": exc.code}) from exc
    except TimeoutError as exc:
        raise HTTPException(504, detail={"code": "RESUME_ANALYSIS_TIMEOUT"}) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503, detail={"code": "DATABASE_ERROR"}) from exc
    finally:
        inference_events.reset(token)


@router.get("/{resume_id}", response_model=ResumeReport)
async def get_resume(resume_id: UUID, request: Request):
    try:
        report = await request.app.state.resume_repository.get(resume_id)
    except SQLAlchemyError as exc:
        raise HTTPException(503, detail={"code": "DATABASE_ERROR"}) from exc
    if report is None:
        raise HTTPException(404, detail={"code": "RESUME_NOT_FOUND"})
    return report
