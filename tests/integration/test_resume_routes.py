from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.llm.router import LLMFailure
from app.main import create_app
from app.schemas.resume import ResumeProfile
from app.tools.resume_pdf import ResumeParseError
from tests.resume_fixtures import make_pdf


@pytest.fixture
def resume_client():
    app = create_app(Settings(_env_file=None, resume_max_bytes=10000))
    with TestClient(app) as client:
        repo = AsyncMock()

        @asynccontextmanager
        async def locked(content_hash):
            yield None

        repo.locked = locked
        repo.get_by_hash.return_value = None
        app.state.resume_repository = repo
        app.state.resume_analyzer = AsyncMock()
        app.state.resume_analyzer.analyze.return_value = (
            ResumeProfile(
                skills=["Python"],
                languages=["Python"],
                frameworks=[],
                blockchain_skills=[],
                backend_skills=[],
                frontend_skills=[],
                infrastructure_skills=[],
                databases=[],
                skill_evidence=[],
                projects=[],
                open_source=[],
                employment=[],
                years_experience=None,
            ),
            [],
        )
        yield client, app, repo


def upload(client, content, content_type="application/pdf"):
    return client.post(
        "/api/v1/resume/analyze", files={"file": ("resume.pdf", content, content_type)}
    )


def test_upload_retrieve_and_cached_skip_parser(resume_client):
    client, app, repo = resume_client
    response = upload(client, make_pdf())
    assert response.status_code == 200
    assert response.json()["profile"]["skills"] == ["Python"]
    report = repo.save.call_args.args[1]
    repo.get.return_value = report
    assert client.get(f"/api/v1/resume/{report.resume_id}").json() == response.json()
    repo.get_by_hash.return_value = report
    app.state.resume_parser = AsyncMock()
    cached = upload(client, make_pdf())
    assert cached.json()["cached"] and cached.json()["resume_id"] == str(report.resume_id)
    app.state.resume_parser.parse.assert_not_called()
    app.state.resume_analyzer.analyze.assert_awaited_once()


@pytest.mark.parametrize(
    "content,mime,status,code",
    [
        (b"", "application/pdf", 422, "EMPTY_FILE"),
        (b"invalid", "application/pdf", 422, "INVALID_PDF"),
        (b"not-pdf", "text/plain", 415, "PDF_REQUIRED"),
        (b"%PDF-" + b"x" * 10000, "application/pdf", 413, "PDF_SIZE_LIMIT"),
        (make_pdf([]), "application/pdf", 422, "OCR_REQUIRED"),
    ],
)
def test_upload_errors(resume_client, content, mime, status, code):
    client, app, repo = resume_client
    response = upload(client, content, mime)
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    repo.save.assert_not_called()
    app.state.resume_analyzer.analyze.assert_not_called()


def test_provider_failure_does_not_save_empty_profile(resume_client):
    client, app, repo = resume_client
    app.state.resume_analyzer.analyze.side_effect = LLMFailure([])
    assert upload(client, make_pdf()).status_code == 502
    repo.save.assert_not_called()


def test_timeout(resume_client):
    client, app, repo = resume_client
    app.state.resume_parser = AsyncMock()
    app.state.resume_parser.parse.side_effect = TimeoutError()
    assert upload(client, make_pdf()).status_code == 504
    repo.save.assert_not_called()


def test_missing_resume(resume_client):
    client, app, repo = resume_client
    repo.get.return_value = None
    assert client.get(f"/api/v1/resume/{uuid4()}").status_code == 404


def test_parse_error_is_safe(resume_client):
    client, app, repo = resume_client
    app.state.resume_parser = AsyncMock()
    app.state.resume_parser.parse.side_effect = ResumeParseError("RESUME_PARSE_FAILED")
    response = upload(client, make_pdf())
    assert response.status_code == 422
    assert response.json()["detail"] == {"code": "RESUME_PARSE_FAILED"}


def test_database_error_is_safe(resume_client):
    client, app, repo = resume_client
    repo.get_by_hash.side_effect = SQLAlchemyError("private database detail")
    response = upload(client, make_pdf())
    assert response.status_code == 503
    assert response.json()["detail"] == {"code": "DATABASE_ERROR"}
    repo.save.assert_not_called()


def test_filename_is_sanitized(resume_client):
    client, app, repo = resume_client
    response = client.post(
        "/api/v1/resume/analyze",
        files={
            "file": ("../../resume.pdf", make_pdf(), "application/pdf"),
        },
    )
    assert response.status_code == 200 and response.json()["filename"] == "resume.pdf"
