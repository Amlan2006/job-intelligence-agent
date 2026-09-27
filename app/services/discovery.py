import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from uuid import uuid4

from app.llm.router import LLMFailure
from app.llm.telemetry import inference_events
from app.schemas.discovery import DiscoveryReport, DiscoveryResult
from app.services.opportunity_scoring import score_opportunity
from app.tools.defillama import FundingSourceError, name_key
from app.tools.webpage import FetchError, validate_public_url


class ResumeNotFound(ValueError):
    pass


class DiscoveryService:
    def __init__(self, source, repository, resumes, opportunities, graph, jobs, timeout):
        self.source, self.repository, self.resumes = source, repository, resumes
        self.opportunities, self.graph, self.jobs, self.timeout = (
            opportunities,
            graph,
            jobs,
            timeout,
        )

    async def run(self, payload):
        resume = await self.resumes.get(payload.resume_id)
        if resume is None:
            raise ResumeNotFound()
        async with self.repository.lock(payload.resume_id):
            await self.repository.recover_interrupted(payload.resume_id)
            report = DiscoveryReport(
                discovery_id=uuid4(),
                resume_id=payload.resume_id,
                started_at=datetime.now(UTC),
                source=payload.source,
            )
            await self.repository.save(report)
            try:
                source = (
                    self.source[payload.source] if isinstance(self.source, dict) else self.source
                )
                source_token = inference_events.set([])
                try:
                    rounds, warnings = await source.fetch(
                        lookback_days=payload.lookback_days,
                        categories=payload.categories,
                        research_run_id=str(report.discovery_id),
                    )
                finally:
                    report.source_inference = [
                        e.model_dump(mode="json") for e in inference_events.get() or []
                    ]
                    inference_events.reset(source_token)
                report.warnings.extend(warnings)
                await self.repository.save(report, rounds)
                cutoff = report.started_at - timedelta(days=payload.lookback_days)
                categories = {name_key(c) for c in payload.categories}
                eligible = [
                    r
                    for r in rounds
                    if r.announced_at
                    and cutoff <= r.announced_at <= report.started_at
                    and (not categories or name_key(r.category or "") in categories)
                ]
                eligible.sort(key=lambda r: (r.announced_at, r.funding_key), reverse=True)
                if not eligible:
                    report.warnings.append("NO_FUNDING_MATCHES: check dates and category filters")
                targets = {name_key(k): v for k, v in payload.targets.items()}
                companies, attempted = set(), 0
                for funding in eligible:
                    funding = funding.model_copy(deep=True)
                    target = targets.get(name_key(funding.company_name))
                    if target:
                        funding.company_url = str(target.company_url)
                        funding.website_basis = "user_supplied"
                        funding.warnings = [
                            w for w in funding.warnings if w != "COMPANY_WEBSITE_UNRESOLVED"
                        ]
                    url = funding.company_url
                    domain = (urlsplit(url).hostname or "").removeprefix("www.") if url else None
                    identity = domain or funding.provider_id or name_key(funding.company_name)
                    if identity in companies:
                        continue  # Most recent eligible round per company per run.
                    companies.add(identity)
                    if not url:
                        if sum(r.status == "unresolved" for r in report.results) < 20:
                            report.results.append(
                                DiscoveryResult(
                                    funding=funding,
                                    status="unresolved",
                                    warnings=["COMPANY_WEBSITE_UNRESOLVED"],
                                )
                            )
                        continue
                    job_url = str(target.job_url) if target and target.job_url else None
                    key = hashlib.sha256(
                        f"v1:{resume.resume_id}:{funding.funding_key}:{domain}:{job_url}".encode()
                    ).hexdigest()
                    if not payload.force_refresh and await self.repository.seen(key):
                        report.skipped_cached += 1
                        continue
                    if attempted >= payload.limit:
                        break
                    attempted += 1
                    run_id = uuid4()
                    token = inference_events.set([])
                    try:
                        async with asyncio.timeout(self.timeout):
                            await validate_public_url(url)
                            if job_url:
                                await validate_public_url(job_url)
                            else:
                                job_url = await self.jobs.find(url)
                            state = await self.graph.ainvoke(
                                {
                                    "company_url": url,
                                    "job_url": job_url,
                                    "resume": resume,
                                    "research_run_id": str(run_id),
                                    "warnings": [],
                                }
                            )
                            opportunity = state["final_report"]
                            ranking = score_opportunity(opportunity, funding, report.started_at)
                            events = [
                                e
                                for e in inference_events.get() or []
                                if e.research_run_id == str(run_id)
                            ]
                            await self.opportunities.save(
                                opportunity, run_id, events, discovery_key=key
                            )
                        report.results.append(
                            DiscoveryResult(
                                funding=funding,
                                status="analyzed",
                                opportunity_id=opportunity.opportunity_id,
                                ranking=ranking,
                                warnings=opportunity.warnings,
                            )
                        )
                    except (FetchError, LLMFailure, TimeoutError, ValueError):
                        report.results.append(
                            DiscoveryResult(
                                funding=funding,
                                status="failed",
                                warnings=["COMPANY_ANALYSIS_FAILED"],
                            )
                        )
                    finally:
                        inference_events.reset(token)
                    await self.repository.save(report)
                report.status = (
                    "partial"
                    if any(r.status != "analyzed" for r in report.results)
                    else "completed"
                )
            except FundingSourceError as exc:
                report.status = "failed"
                report.warnings.append(str(exc))
            except asyncio.CancelledError:
                report.status = "partial"
                report.warnings.append("DISCOVERY_INTERRUPTED")
                report.finished_at = datetime.now(UTC)
                await self.repository.save(report)
                raise
            report.results.sort(
                key=lambda r: r.ranking.score if r.ranking and r.ranking.score is not None else -1,
                reverse=True,
            )
            report.finished_at = datetime.now(UTC)
            await self.repository.save(report)
            return report
