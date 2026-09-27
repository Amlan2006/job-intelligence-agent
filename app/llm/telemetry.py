import logging

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class InferenceEvent(BaseModel):
    research_run_id: str
    agent_name: str
    task_type: str
    provider: str
    model: str
    latency_ms: float
    fallback_used: bool
    success: bool
    input_tokens: int | None = None
    output_tokens: int | None = None
    error_code: str | None = None


def log_inference(event: InferenceEvent) -> None:
    # Never log prompts, resume contents, credentials, or raw provider errors.
    logger.info("llm_inference", extra={"metadata": event.model_dump()})
