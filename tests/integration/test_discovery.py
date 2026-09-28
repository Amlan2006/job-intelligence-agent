import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schemas.discovery import DiscoveryRequest, DiscoveryTarget
from app.tools.defillama import FundingSourceError
from app.tools.webpage import FetchError
from tests.discovery_fixtures import funding, service


@pytest.fixture(autouse=True)
def public_urls(monkeypatch):
    monkeypatch.setattr("app.services.discovery.validate_public_url", AsyncMock())


async def test_resume_scoped_cache_force_refresh_and_bounded_research():
    runner, resume = service()
    payload = DiscoveryRequest(resume_id=resume.resume_id)
    report = await runner.run(payload)
    assert report.results[0].ranking.score == 20
    assert report.status == "completed"
    repeated = await runner.run(payload)
    assert repeated.skipped_cached == 1 and repeated.results == []
    assert runner.graph.ainvoke.await_count == 1
    await runner.run(payload.model_copy(update={"force_refresh": True}))
    assert runner.graph.ainvoke.await_count == 2
    resume.resume_id = uuid4()
    await runner.run(DiscoveryRequest(resume_id=resume.resume_id))
    assert runner.graph.ainvoke.await_count == 3


async def test_job_board_source_passes_listing_to_opportunity_graph():
    runner, resume = service()
    source = runner.source
    source.fetch.return_value[0][0].job_url = "https://board.example/jobs/engineer"
    runner.source = {"job_boards": source}
    report = await runner.run(DiscoveryRequest(resume_id=resume.resume_id, source="job_boards"))
    assert report.source == "job_boards"
    assert (
        runner.graph.ainvoke.call_args.args[0]["job_url"] == "https://board.example/jobs/engineer"
    )
    runner.jobs.find.assert_not_called()


async def test_verified_first_and_unverified_visible_beyond_research_limit():
    runner, resume = service()
    runner.source.fetch.return_value = (
        [
            funding(
                funding_status="unverified",
                funding_key="unknown",
                company_name="Other",
                company_url="https://other.example",
                announced_at=None,
            ),
            funding(),
        ],
        [],
    )
    report = await runner.run(DiscoveryRequest(resume_id=resume.resume_id, limit=1))
    assert [r.funding.funding_status for r in report.results] == ["verified", "unverified"]
    assert report.results[1].status == "discovered"
    assert runner.graph.ainvoke.await_count == 1


async def test_unverified_can_be_researched_without_funding_credit():
    runner, resume = service()
    runner.source.fetch.return_value = (
        [funding(funding_status="unverified", announced_at=None)],
        [],
    )
    report = await runner.run(DiscoveryRequest(resume_id=resume.resume_id))
    assert report.results[0].status == "analyzed"
    assert report.results[0].ranking.components["recent_funding"] is None


async def test_unreachable_observed_website_remains_visible_without_research():
    runner, resume = service()
    runner.source.fetch.return_value = (
        [
            funding(
                provider="job_boards",
                website_status="unreachable",
                funding_status="unverified",
                announced_at=None,
            )
        ],
        [],
    )
    report = await runner.run(DiscoveryRequest(resume_id=resume.resume_id))
    assert report.results[0].status == "discovered"
    assert report.results[0].funding.company_url
    runner.graph.ainvoke.assert_not_called()


async def test_filter_duplicates_recent_category_future_and_unresolved():
    runner, resume = service()
    runner.source.fetch.return_value = (
        [
            funding(),
            funding(funding_key="duplicate"),
            funding(funding_key="old", announced_at=datetime.now(UTC) - timedelta(days=200)),
            funding(funding_key="future", announced_at=datetime.now(UTC) + timedelta(days=1)),
            funding(funding_key="other", category="Gaming"),
            funding(funding_key="missing", company_name="Unknown", company_url=None),
        ],
        [],
    )
    report = await runner.run(DiscoveryRequest(resume_id=resume.resume_id, categories=["defi"]))
    assert runner.graph.ainvoke.await_count == 1
    assert {r.status for r in report.results} == {"analyzed", "unresolved"}
    assert report.status == "partial"


async def test_cached_companies_do_not_consume_next_batch_limit():
    runner, resume = service()
    payload = DiscoveryRequest(resume_id=resume.resume_id, limit=1)
    await runner.run(payload)
    first = runner.source.fetch.return_value[0][0]
    runner.source.fetch.return_value = (
        [
            first,
            funding(
                funding_key="next",
                company_url="https://next.example",
                announced_at=first.announced_at - timedelta(days=1),
            ),
        ],
        [],
    )
    report = await runner.run(payload)
    assert report.skipped_cached == 1 and len(report.results) == 1
    assert report.results[0].funding.funding_key == "next"


@pytest.mark.parametrize("error", [TimeoutError(), FetchError("private detail")])
async def test_individual_failure_preserves_progress_and_is_retryable(error):
    runner, resume = service()
    runner.graph.ainvoke.side_effect = error
    report = await runner.run(DiscoveryRequest(resume_id=resume.resume_id))
    assert report.status == "partial" and report.results[0].status == "failed"
    assert not runner.repository.keys
    assert "private detail" not in report.model_dump_json()


async def test_missing_provider_key_persisted_and_no_research():
    runner, resume = service()
    runner.source.fetch.side_effect = FundingSourceError("DEFILLAMA_API_KEY_REQUIRED")
    report = await runner.run(DiscoveryRequest(resume_id=resume.resume_id))
    assert report.status == "failed" and report.finished_at
    assert (await runner.repository.get(report.discovery_id)).status == "failed"
    runner.graph.ainvoke.assert_not_called()


async def test_tavily_default_and_explicit_defillama_selection():
    runner, resume = service()
    tavily, defillama = runner.source, AsyncMock()
    defillama.fetch.return_value = ([], [])
    runner.source = {"tavily": tavily, "defillama": defillama}
    report = await runner.run(DiscoveryRequest(resume_id=resume.resume_id))
    assert report.source == "tavily"
    tavily.fetch.assert_awaited_once()
    defillama.fetch.assert_not_called()
    report = await runner.run(DiscoveryRequest(resume_id=resume.resume_id, source="defillama"))
    assert report.source == "defillama"
    defillama.fetch.assert_awaited_once()


async def test_explicit_target_supplies_missing_website_and_job():
    runner, resume = service()
    runner.source.fetch.return_value = ([funding(company_url=None)], [])
    payload = DiscoveryRequest(
        resume_id=resume.resume_id,
        targets={
            "Example Labs": DiscoveryTarget(
                company_url="https://example.com", job_url="https://example.com/jobs/python"
            )
        },
    )
    report = await runner.run(payload)
    assert report.results[0].funding.website_basis == "user_supplied"
    assert runner.graph.ainvoke.call_args.args[0]["job_url"] == "https://example.com/jobs/python"
    runner.jobs.find.assert_not_called()


async def test_cancellation_is_saved():
    runner, resume = service()
    runner.graph.ainvoke.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await runner.run(DiscoveryRequest(resume_id=resume.resume_id))
    report = next(iter(runner.repository.saved.values()))
    assert report.status == "partial" and "DISCOVERY_INTERRUPTED" in report.warnings


def test_api_run_history_missing_and_validation():
    app = create_app(Settings(_env_file=None))
    with TestClient(app) as client:
        runner, resume = service()
        app.state.discovery_service = runner
        app.state.discovery_repository = runner.repository
        response = client.post("/api/v1/discovery/run", json={"resume_id": str(resume.resume_id)})
        assert response.status_code == 200
        run_id = response.json()["discovery_id"]
        assert client.get(f"/api/v1/discovery/runs/{run_id}").json() == response.json()
        assert (
            len(
                client.get(
                    "/api/v1/discovery/runs", params={"resume_id": str(resume.resume_id)}
                ).json()
            )
            == 1
        )
        assert client.get(f"/api/v1/discovery/runs/{uuid4()}").status_code == 404
        assert (
            client.post(
                "/api/v1/discovery/run", json={"resume_id": str(resume.resume_id), "limit": 100}
            ).status_code
            == 422
        )
        runner.resumes.get.return_value = None
        assert (
            client.post(
                "/api/v1/discovery/run", json={"resume_id": str(resume.resume_id)}
            ).status_code
            == 404
        )
