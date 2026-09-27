import logging

from langgraph.graph import END, START, StateGraph

from app.graph.state import AgentState
from app.llm.base import Message
from app.llm.router import LLMFailure, LLMRouter
from app.llm.schemas import FoundationResult

logger = logging.getLogger(__name__)


def build_foundation_graph(llm: LLMRouter):
    async def foundation_node(state: AgentState) -> dict:
        metadata = {"research_run_id": state["research_run_id"], "node_name": "foundation"}
        logger.info("node_started", extra={"metadata": metadata})
        try:
            result = await llm.invoke(
                [Message(role="user", content=state["prompt"])],
                schema=FoundationResult,
                task_type="foundation_check",
                agent_name="foundation",
                research_run_id=state["research_run_id"],
            )
        except LLMFailure as error:
            logger.warning("node_failed", extra={"metadata": metadata | {"error_code": error.code}})
            return {"errors": [{"code": error.code, "message": str(error)}]}
        logger.info("node_completed", extra={"metadata": metadata})
        return {"result": result.model_dump(), "errors": []}

    graph = StateGraph(AgentState)
    graph.add_node("foundation", foundation_node)
    graph.add_edge(START, "foundation")
    graph.add_edge("foundation", END)
    return graph.compile()
