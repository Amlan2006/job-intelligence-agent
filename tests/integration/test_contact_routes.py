from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.contact_fixtures import contact
from tests.opportunity_fixtures import company_report


@pytest.fixture
def contact_client():
    application = create_app(Settings(_env_file=None))
    with TestClient(application) as client:
        company = company_report()
        application.state.company_repository = AsyncMock()
        application.state.company_repository.latest_report.return_value = company
        application.state.contact_repository = AsyncMock()
        application.state.contact_finder = AsyncMock()
        application.state.contact_finder.discover.return_value = ([contact()], [])
        yield client, application, company


def test_discover_store_and_retrieve(contact_client):
    client, app, company = contact_client
    response = client.post(f"/api/v1/company/{company.company_id}/contacts/discover", json={})
    assert response.status_code == 200 and len(response.json()["contacts"]) == 1
    app.state.contact_repository.latest.return_value = (
        app.state.contact_repository.save.call_args.args[0]
    )
    assert client.get(f"/api/v1/company/{company.company_id}/contacts").json() == response.json()


def test_risky_company_contact_discovery_withheld(contact_client):
    client, app, company = contact_client
    company.assessment = "High-risk signals detected"
    assert (
        client.post(f"/api/v1/company/{company.company_id}/contacts/discover", json={}).status_code
        == 409
    )
    app.state.contact_finder.discover.assert_not_called()


def test_no_contact_snapshot(contact_client):
    client, app, company = contact_client
    app.state.contact_repository.latest.return_value = None
    assert client.get(f"/api/v1/company/{uuid4()}/contacts").status_code == 404


def test_missing_resume(contact_client):
    client, app, company = contact_client
    app.state.resume_repository = AsyncMock()
    app.state.resume_repository.get.return_value = None
    assert (
        client.post(
            f"/api/v1/company/{company.company_id}/contacts/discover",
            json={"resume_id": str(uuid4())},
        ).status_code
        == 404
    )
