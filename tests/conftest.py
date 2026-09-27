from unittest.mock import AsyncMock

import pytest

from app.llm.base import ProviderResponse


@pytest.fixture
def providers():
    primary = AsyncMock(name="primary")
    primary.name, primary.model = "codex", "cli-default"
    fallback = AsyncMock(name="fallback")
    fallback.name, fallback.model = "groq", "test-model"
    primary.invoke.return_value = ProviderResponse(content='{"message":"primary"}')
    fallback.invoke.return_value = ProviderResponse(content='{"message":"fallback"}')
    return primary, fallback
