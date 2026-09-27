import asyncio
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.agents.outreach_writer import OutreachUnavailable
from app.llm.router import LLMFailure
from app.llm.telemetry import inference_events
from app.schemas.opportunity import OpportunityReport
from app.services.embeddings import EmbeddingError
from app.services.skill_matching import match_skills
from app.tools.webpage import FetchError


class OpportunityState(TypedDict, total=False):
    company_url: str
    job_url: str | None
    resume: object
    research_run_id: str
    company: object
    job: object
    vectors: dict
    match: object
    warnings: list[str]
    final_report: OpportunityReport
    contacts: list
    outreach: object
    opportunity_id: object


def build_opportunity_graph(
    company_graph,
    company_repository,
    job_analyzer,
    embeddings,
    embedding_repository,
    threshold: float,
    contact_finder=None,
    outreach_writer=None,
):
    async def research_company(state):
        run_id = str(uuid4())
        from urllib.parse import urlsplit

        company_id = await company_repository.company_id(urlsplit(state["company_url"]).hostname)
        company_state = await company_graph.ainvoke(
            {
                "company_url": state["company_url"],
                "research_run_id": run_id,
                "company_id": company_id,
            }
        )
        report = company_state["final_report"]
        events = [
            event for event in inference_events.get() or [] if event.research_run_id == run_id
        ]
        await company_repository.save(report, events)
        return {"company": report, "warnings": list(report.warnings), "opportunity_id": uuid4()}

    def route_after_company(state):
        if state["company"].assessment in {"High-risk signals detected", "Insufficient evidence"}:
            return "withhold_matching"
        if not state.get("job_url"):
            return "no_job"
        return "analyze_job"

    def withhold_matching(state):
        return {
            "warnings": state["warnings"] + ["MATCH_WITHHELD: company evidence requires review"]
        }

    def no_job(state):
        return {"warnings": state["warnings"] + ["JOB_NOT_PROVIDED: skill match unavailable"]}

    async def analyze_job(state):
        warnings = list(state["warnings"])
        try:
            job = await job_analyzer.analyze(state["job_url"], state["research_run_id"])
            warnings.extend(job.warnings)
            # Third-party job boards are allowed; employer association remains user-reviewable.
            company_name = state["company"].company_name or ""
            if not job.company or job.company.casefold() != company_name.casefold():
                warnings.append("COMPANY_JOB_ASSOCIATION_UNVERIFIED: check the job's employer")
            return {"job": job, "warnings": warnings}
        except FetchError:
            warnings.append("JOB_FETCH_FAILED: company report returned without a job match")
        except LLMFailure:
            warnings.append("JOB_ANALYSIS_FAILED: company report returned without a job match")
        return {"job": None, "warnings": warnings}

    async def embed_skills(state):
        if not state.get("job") or not state["job"].requirements:
            return {"vectors": {}}
        texts = sorted(
            set(state["resume"].profile.skills + [r.skill for r in state["job"].requirements])
        )
        vectors = await embedding_repository.get(texts, embeddings.model)
        missing = [text for text in texts if text not in vectors]
        warnings = list(state["warnings"])
        try:
            generated = await embeddings.embed(missing)
            await embedding_repository.save(generated, embeddings.model)
            vectors.update(generated)
        except (EmbeddingError, TimeoutError, OSError):
            warnings.append("EMBEDDINGS_UNAVAILABLE: matching uses exact, alias and related skills")
        return {"vectors": vectors, "warnings": warnings}

    def match_resume(state):
        if not state.get("job"):
            return {"match": None}
        match = match_skills(state["resume"].profile, state["job"], state.get("vectors"), threshold)
        return {"match": match, "warnings": state["warnings"] + match.warnings}

    def generate_report(state):
        report = OpportunityReport(
            opportunity_id=state["opportunity_id"],
            resume_id=state["resume"].resume_id,
            company=state["company"],
            job=state.get("job"),
            match=state.get("match"),
            warnings=list(dict.fromkeys(state["warnings"])),
            contacts=state.get("contacts", []),
            outreach=state.get("outreach"),
        )
        return {"final_report": report}

    async def generate_outreach(state):
        if outreach_writer is None or not state.get("contacts"):
            return {}
        # Draft only for the top-ranked contact; selecting another contact is an explicit API call.
        opportunity = generate_report(state)["final_report"]
        try:
            async with asyncio.timeout(outreach_writer.timeout):
                report = await outreach_writer.generate(
                    opportunity, state["resume"], 0, state["research_run_id"]
                )
            return {"outreach": report}
        except (OutreachUnavailable, LLMFailure, TimeoutError):
            return {
                "warnings": state["warnings"] + ["OUTREACH_UNAVAILABLE: manual review required"]
            }

    async def find_contacts(state):
        if contact_finder is None:
            return {"contacts": []}
        try:
            async with asyncio.timeout(contact_finder.timeout):
                contacts, warnings = await contact_finder.discover(
                    state["company"], state["resume"].profile.skills, state["research_run_id"]
                )
            return {"contacts": contacts, "warnings": state["warnings"] + warnings}
        except TimeoutError:
            return {"contacts": [], "warnings": state["warnings"] + ["CONTACT_DISCOVERY_TIMEOUT"]}

    graph = StateGraph(OpportunityState)
    for name, node in (
        ("research_company", research_company),
        ("analyze_job", analyze_job),
        ("embed_skills", embed_skills),
        ("match_skills", match_resume),
        ("withhold_matching", withhold_matching),
        ("no_job", no_job),
        ("generate_report", generate_report),
        ("find_contacts", find_contacts),
        ("generate_outreach", generate_outreach),
    ):
        graph.add_node(name, node)
    graph.add_edge(START, "research_company")
    graph.add_conditional_edges(
        "research_company", route_after_company, ["analyze_job", "withhold_matching", "no_job"]
    )
    graph.add_edge("analyze_job", "embed_skills")
    graph.add_edge("embed_skills", "match_skills")
    graph.add_edge("match_skills", "find_contacts")
    graph.add_edge("find_contacts", "generate_outreach")
    graph.add_edge("generate_outreach", "generate_report")
    graph.add_edge("withhold_matching", "generate_report")
    graph.add_edge("no_job", "find_contacts")
    graph.add_edge("generate_report", END)
    return graph.compile()
