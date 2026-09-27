from typing import TypedDict


class AgentState(TypedDict, total=False):
    research_run_id: str
    prompt: str
    result: dict
    errors: list[dict[str, str]]
    warnings: list[str]
