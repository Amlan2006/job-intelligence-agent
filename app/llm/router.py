import asyncio
from time import perf_counter
from typing import Callable

from pydantic import BaseModel, ValidationError

from app.llm.base import LLMProvider, Message
from app.llm.telemetry import InferenceEvent, log_inference


class LLMFailure(RuntimeError):
    code = "ALL_LLM_PROVIDERS_FAILED"

    def __init__(self, failures: list[InferenceEvent]):
        super().__init__("All LLM providers failed")
        self.failures = failures


class LLMRouter:
    def __init__(
        self,
        primary: LLMProvider,
        fallback: LLMProvider,
        timeout: float = 30,
        fallback_timeout: float = 30,
        telemetry: Callable[[InferenceEvent], None] = log_inference,
    ):
        self.primary, self.fallback = primary, fallback
        self.timeouts = (timeout, fallback_timeout)
        self.telemetry = telemetry

    async def invoke(
        self,
        messages: list[Message],
        schema: type[BaseModel] | None = None,
        task_type: str = "unspecified",
        agent_name: str = "unspecified",
        research_run_id: str = "unspecified",
    ) -> BaseModel | str:
        failures = []
        for index, provider in enumerate((self.primary, self.fallback)):
            start = perf_counter()
            response = None
            error_code = None
            try:
                async with asyncio.timeout(self.timeouts[index]):
                    response = await provider.invoke(messages, schema=schema, task_type=task_type)
                if not response.content.strip():
                    raise ValueError("Empty provider output")
                result = (
                    schema.model_validate_json(response.content) if schema else response.content
                )
            except TimeoutError:
                error_code = "LLM_TIMEOUT"
            except (ValidationError, ValueError):
                error_code = "STRUCTURED_OUTPUT_INVALID"
            except Exception:
                error_code = "LLM_PROVIDER_FAILED"
            event = InferenceEvent(
                research_run_id=research_run_id,
                agent_name=agent_name,
                task_type=task_type,
                provider=provider.name,
                model=provider.model,
                latency_ms=round((perf_counter() - start) * 1000, 2),
                fallback_used=bool(index),
                success=error_code is None,
                error_code=error_code,
                input_tokens=response.input_tokens if response else None,
                output_tokens=response.output_tokens if response else None,
            )
            self.telemetry(event)
            if error_code is None:
                return result
            failures.append(event)
        raise LLMFailure(failures)
