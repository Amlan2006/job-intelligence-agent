from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.graph.opportunity import build_opportunity_graph
from app.main import create_app
from app.services.embeddings import EmbeddingError
from app.tools.webpage import FetchError
from tests.opportunity_fixtures import company_report, job_profile, resume_report


@pytest.fixture
def opportunity_client(monkeypatch):
    monkeypatch.setattr("app.api.routes_opportunity.validate_public_url", AsyncMock())
    app = create_app(Settings(_env_file=None))
    with TestClient(app) as client:
        resume = resume_report()
        company_graph, company_repo, job, embeddings, cache, repo = [AsyncMock() for _ in range(6)]
        company_graph.ainvoke.return_value = {"final_report": company_report()}
        company_repo.company_id.return_value = company_report().company_id
        job.analyze.return_value = job_profile()
        embeddings.model = "fixture-model"
        embeddings.embed.return_value = {}
        cache.get.return_value = {}
        app.state.resume_repository = AsyncMock()
        app.state.resume_repository.get.return_value = resume
        app.state.opportunity_repository = repo
        app.state.opportunity_graph = build_opportunity_graph(
            company_graph, company_repo, job, embeddings, cache, 0.88
        )
        yield client, app, resume, job, embeddings, repo, company_graph


def analyze(client, resume, **updates):
    return client.post(
        "/api/v1/opportunity/analyze",
        json={
            "company_url": "https://example.com",
            "job_url": "https://example.com/jobs/1",
            "resume_id": str(resume.resume_id),
            **updates,
        },
    )


def test_complete_graph_and_retrieval(opportunity_client):
    client, app, resume, job, embeddings, repo, _ = opportunity_client
    response = analyze(client, resume)
    assert response.status_code == 200
    report = response.json()
    assert report["match"]["overall_score"] is not None
    assert report["match"]["missing_requirements"][0]["requirement"] == "Redis"
    saved = repo.save.call_args.args[0]
    repo.get.return_value = saved
    repo.list.return_value = [saved]
    assert client.get(f"/api/v1/opportunities/{report['opportunity_id']}").json() == report
    assert client.get("/api/v1/opportunities").json() == [report]


def test_no_job_no_invented_score(opportunity_client):
    client, app, resume, job, embeddings, repo, _ = opportunity_client
    response = analyze(client, resume, job_url=None)
    assert response.status_code == 200 and response.json()["match"] is None
    job.analyze.assert_not_called()


def test_risky_company_stops_before_job_analysis(opportunity_client):
    client, app, resume, job, embeddings, repo, company_graph = opportunity_client
    company_graph.ainvoke.return_value = {
        "final_report": company_report("High-risk signals detected")
    }
    report = analyze(client, resume).json()
    assert report["match"] is None and any(
        "MATCH_WITHHELD" in warning for warning in report["warnings"]
    )
    job.analyze.assert_not_called()


def test_missing_resume(opportunity_client):
    client, app, resume, *_ = opportunity_client
    app.state.resume_repository.get.return_value = None
    assert analyze(client, resume).status_code == 404


def test_embedding_failure_keeps_deterministic_matches(opportunity_client):
    client, app, resume, job, embeddings, repo, _ = opportunity_client
    embeddings.embed.side_effect = EmbeddingError("private detail")
    response = analyze(client, resume)
    assert response.status_code == 200
    assert response.json()["match"]["strong_matches"]
    assert any("EMBEDDINGS_UNAVAILABLE" in warning for warning in response.json()["warnings"])


def test_unknown_opportunity(opportunity_client):
    client, app, resume, job, embeddings, repo, _ = opportunity_client
    repo.get.return_value = None
    assert client.get(f"/api/v1/opportunities/{uuid4()}").status_code == 404


def test_job_fetch_failure_returns_company_report(opportunity_client):
    client, app, resume, job, embeddings, repo, _ = opportunity_client
    job.analyze.side_effect = FetchError("private detail")
    response = analyze(client, resume)
    assert response.status_code == 200
    assert response.json()["company"] and response.json()["job"] is None
    assert response.json()["match"] is None
    assert any("JOB_FETCH_FAILED" in warning for warning in response.json()["warnings"])


def test_database_error_sanitized(opportunity_client):
    client, app, resume, job, embeddings, repo, _ = opportunity_client
    app.state.resume_repository.get.side_effect = SQLAlchemyError("private database detail")
    response = analyze(client, resume)
    assert response.status_code == 503 and "private database detail" not in response.text


def test_invalid_public_url_rejected(opportunity_client, monkeypatch):
    client, app, resume, *_ = opportunity_client
    monkeypatch.setattr(
        "app.api.routes_opportunity.validate_public_url",
        AsyncMock(side_effect=FetchError("Private destination")),
    )
    assert analyze(client, resume).status_code == 422


def test_total_timeout_sanitized(opportunity_client):
    client, app, resume, job, embeddings, repo, graph = opportunity_client
    graph.ainvoke.side_effect = TimeoutError()
    response = analyze(client, resume)
    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "OPPORTUNITY_TIMEOUT"
