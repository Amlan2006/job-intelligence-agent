from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.llm.router import LLMFailure
from app.main import create_app
from tests.unit.agents.test_outreach_writer import inputs, writer


@pytest.fixture
def setup():
    app = create_app(Settings(_env_file=None))
    with TestClient(app) as client:
        opportunity, resume = inputs()
        app.state.opportunity_repository = AsyncMock()
        app.state.opportunity_repository.get.return_value = opportunity
        app.state.resume_repository = AsyncMock()
        app.state.resume_repository.get.return_value = resume
        app.state.outreach_repository = AsyncMock()
        app.state.outreach_writer = writer()
        yield client, app, opportunity


def post(client, opportunity, **extra):
    return client.post(
        "/api/v1/outreach/generate",
        json={
            "opportunity_id": str(opportunity.opportunity_id),
            **extra,
        },
    )


def test_save_and_retrieve(setup):
    client, app, opportunity = setup
    result = post(client, opportunity)
    assert result.status_code == 200
    report = app.state.outreach_repository.save.call_args.args[0]
    app.state.outreach_repository.get.return_value = report
    assert client.get(f"/api/v1/outreach/{report.outreach_id}").json() == result.json()


@pytest.mark.parametrize(
    "case,code",
    [
        ("opportunity", 404),
        ("resume", 404),
        ("contact", 409),
        ("llm", 502),
        ("timeout", 504),
        ("database", 503),
    ],
)
def test_failures(setup, case, code):
    client, app, opportunity = setup
    if case == "opportunity":
        app.state.opportunity_repository.get.return_value = None
    elif case == "resume":
        app.state.resume_repository.get.return_value = None
    elif case == "contact":
        opportunity.contacts = []
    elif case == "llm":
        app.state.outreach_writer.llm.invoke.side_effect = LLMFailure([])
    elif case == "timeout":
        app.state.outreach_writer.llm.invoke.side_effect = TimeoutError()
    else:
        app.state.outreach_repository.save.side_effect = SQLAlchemyError("secret")
    response = post(client, opportunity)
    assert response.status_code == code and "secret" not in response.text
    if case != "database":
        app.state.outreach_repository.save.assert_not_called()


def test_validation_and_missing_snapshot(setup):
    client, app, opportunity = setup
    assert post(client, opportunity, contact_index=-1).status_code == 422
    app.state.outreach_repository.get.return_value = None
    assert client.get(f"/api/v1/outreach/{uuid4()}").status_code == 404
