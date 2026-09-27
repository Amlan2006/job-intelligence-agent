import logging
from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from app.agents.company_research import CompanyResearchAgent
from app.schemas.company import CompanyReport
from app.services.company_scoring import score_company

logger = logging.getLogger(__name__)


class CompanyState(TypedDict, total=False):
    company_url: str
    research_run_id: str
    company_id: UUID
    research: dict
    scoring: tuple
    final_report: CompanyReport


def build_company_graph(agent: CompanyResearchAgent, weights: dict | None = None):
    async def research_company(state):
        logger.info(
            "node_started",
            extra={
                "metadata": {
                    "research_run_id": state["research_run_id"],
                    "node_name": "research_company",
                }
            },
        )
        return {"research": await agent.research(state["company_url"], state["research_run_id"])}

    def score_legitimacy(state):
        return {"scoring": score_company(state["research"]["evidence"], weights)}

    def generate_report(state):
        from urllib.parse import urlsplit

        research = state["research"]
        score, assessment, positives, risks = state["scoring"]
        report = CompanyReport(
            research_id=state["research_run_id"],
            company_id=state["company_id"],
            company_domain=urlsplit(state["company_url"]).hostname,
            company_name=research["company_name"],
            company_description=research["company_description"],
            legitimacy_score=score,
            assessment=assessment,
            positive_signals=positives,
            risk_signals=risks,
            evidence=research["evidence"],
            funding_information=[
                item for item in research["evidence"] if item.evidence_type == "funding_confirmed"
            ],
            sources=list(dict.fromkeys(source.source_url for source in research["sources"])),
            warnings=research["warnings"],
        )
        return {"final_report": report}

    graph = StateGraph(CompanyState)
    graph.add_node("research_company", research_company)
    graph.add_node("score_legitimacy", score_legitimacy)
    graph.add_node("generate_report", generate_report)
    graph.add_edge(START, "research_company")
    graph.add_edge("research_company", "score_legitimacy")
    graph.add_edge("score_legitimacy", "generate_report")
    graph.add_edge("generate_report", END)
    return graph.compile()
