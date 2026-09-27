from app.llm.router import LLMRouter
from app.llm.schemas import FoundationResult
from app.llm.telemetry import inference_events


async def test_request_scoped_events_include_failure_and_fallback(providers):
    primary, fallback = providers
    primary.invoke.side_effect = RuntimeError("private detail")
    events = []
    token = inference_events.set(events)
    try:
        await LLMRouter(primary, fallback).invoke(
            [], schema=FoundationResult, research_run_id="research-1"
        )
    finally:
        inference_events.reset(token)
    assert len(events) == 2
    assert events[0].research_run_id == "research-1"
    assert not events[0].success and events[1].fallback_used and events[1].success
    assert inference_events.get() is None
