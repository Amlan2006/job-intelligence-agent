import httpx
import pytest

from app.llm.groq import GroqProvider
from app.llm.schemas import FoundationResult


async def test_groq_request_and_usage():
    def handle(request):
        assert request.headers["authorization"] == "Bearer test-key"
        assert b'"response_format":{"type":"json_object"}' in request.content
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"message":"ok"}'}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 3},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await GroqProvider(client, "test-key", "test-model", 30).invoke(
            [], FoundationResult
        )
    assert result.input_tokens == 4


async def test_groq_requires_configuration():
    async with httpx.AsyncClient() as client:
        with pytest.raises(RuntimeError, match="not configured"):
            await GroqProvider(client, "", "", 30).invoke([])
