import asyncio

import pytest

from app.llm.base import Message, ProviderResponse
from app.llm.router import LLMFailure, LLMRouter
from app.llm.schemas import FoundationResult


async def test_primary_success(providers):
    primary, fallback = providers
    events = []
    result = await LLMRouter(primary, fallback, telemetry=events.append).invoke(
        [Message(role="user", content="check")],
        schema=FoundationResult,
    )
    assert result.message == "primary"
    fallback.invoke.assert_not_called()
    assert events[0].success and not events[0].fallback_used


@pytest.mark.parametrize(
    "content", ["", "   ", "not json", "{}", '{"message": 1}', '{"message":"ok","invented":true}']
)
async def test_invalid_primary_falls_back(providers, content):
    primary, fallback = providers
    primary.invoke.return_value = ProviderResponse(content=content)
    events = []
    result = await LLMRouter(primary, fallback, telemetry=events.append).invoke(
        [],
        schema=FoundationResult,
    )
    assert result.message == "fallback"
    assert events[0].error_code == "STRUCTURED_OUTPUT_INVALID"
    assert events[1].success and events[1].fallback_used


async def test_exception_falls_back(providers):
    primary, fallback = providers
    primary.invoke.side_effect = RuntimeError("private detail")
    assert (
        await LLMRouter(primary, fallback).invoke([], schema=FoundationResult)
    ).message == "fallback"


async def test_timeout_falls_back(providers):
    primary, fallback = providers

    async def slow(*args, **kwargs):
        await asyncio.sleep(10)

    primary.invoke.side_effect = slow
    events = []
    router = LLMRouter(primary, fallback, timeout=0.01, telemetry=events.append)
    assert (await router.invoke([], schema=FoundationResult)).message == "fallback"
    assert events[0].error_code == "LLM_TIMEOUT"


async def test_both_fail(providers):
    primary, fallback = providers
    primary.invoke.side_effect = RuntimeError("secret")
    fallback.invoke.return_value = ProviderResponse(content="bad json")
    with pytest.raises(LLMFailure) as failure:
        await LLMRouter(primary, fallback).invoke([], schema=FoundationResult)
    assert len(failure.value.failures) == 2
    assert "secret" not in str(failure.value)


async def test_cancellation_does_not_trigger_fallback(providers):
    primary, fallback = providers
    primary.invoke.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await LLMRouter(primary, fallback).invoke([])
    fallback.invoke.assert_not_called()
