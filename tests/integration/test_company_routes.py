from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.graph.company import build_company_graph
from app.main import create_app
from app.schemas.evidence import Evidence
from app.tools.webpage import FetchError


@pytest.fixture
def company_client(monkeypatch):
    monkeypatch.setattr("app.api.routes_company.validate_public_url", AsyncMock())
    app = create_app(Settings(_env_file=None))
    with TestClient(app) as client:
        agent = AsyncMock()
        agent.research.return_value = {
            "company_name": "Example",
            "company_description": "Developer tools",
            "evidence": [
                Evidence(
                    evidence_type="website",
                    source_name="Example",
                    source_url="https://example.com",
                    claim="Site accessible",
                    confidence=1,
                    retrieved_at=datetime.now(UTC),
                )
            ],
            "sources": [],
            "warnings": [],
        }
        repo = AsyncMock()
        repo.company_id.return_value = uuid4()
        app.state.company_graph = build_company_graph(agent)
        app.state.company_repository = repo
        yield client, repo


def test_report_and_retrieval(company_client):
    client, repo = company_client
    response = client.post("/api/v1/research/company", json={"company_url": "https://example.com"})
    assert response.status_code == 200
    report = response.json()
    assert report["legitimacy_score"] == 10
    repo.save.assert_awaited_once()
    repo.get_report.return_value = repo.save.call_args.args[0]
    repo.latest_report.return_value = repo.save.call_args.args[0]
    assert client.get(f"/api/v1/research/{report['research_id']}").json() == report
    assert client.get(f"/api/v1/company/{report['company_id']}").json() == report
    assert len(client.get(f"/api/v1/company/{report['company_id']}/evidence").json()) == 1


def test_unknown_report(company_client):
    client, repo = company_client
    repo.get_report.return_value = None
    assert client.get(f"/api/v1/research/{uuid4()}").status_code == 404


def test_private_url_rejected(company_client, monkeypatch):
    client, repo = company_client
    monkeypatch.setattr(
        "app.api.routes_company.validate_public_url",
        AsyncMock(side_effect=FetchError("Private URL")),
    )
    assert (
        client.post(
            "/api/v1/research/company", json={"company_url": "http://localhost"}
        ).status_code
        == 422
    )
    repo.company_id.assert_not_called()


def test_database_error_sanitized(company_client):
    client, repo = company_client
    repo.company_id.side_effect = SQLAlchemyError("private database details")
    response = client.post("/api/v1/research/company", json={"company_url": "https://example.com"})
    assert response.status_code == 503 and "private database" not in response.text
