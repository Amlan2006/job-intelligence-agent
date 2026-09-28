from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from app.db.repositories.opportunity import EmbeddingRepository


@pytest.mark.parametrize(
    "vector",
    [[0.25, -0.5, 1.0], np.array([0.25, -0.5, 1.0], dtype=np.float32)],
    ids=["python-list", "numpy-array"],
)
async def test_cached_embeddings_normalize_driver_return_types(vector):
    session = AsyncMock()
    session.scalars.return_value = MagicMock()
    session.scalars.return_value.all.return_value = [
        SimpleNamespace(text="Python", embedding=vector),
    ]
    sessions = MagicMock()
    sessions.return_value.__aenter__.return_value = session

    result = await EmbeddingRepository(sessions).get(["Python"], "test-model")

    assert result == {"Python": [0.25, -0.5, 1.0]}
    assert isinstance(result["Python"], list)
    assert all(type(value) is float for value in result["Python"])
    session.scalars.assert_awaited_once()


async def test_missing_cached_embeddings_return_empty_mapping():
    session = AsyncMock()
    session.scalars.return_value = MagicMock()
    session.scalars.return_value.all.return_value = []
    sessions = MagicMock()
    sessions.return_value.__aenter__.return_value = session

    assert await EmbeddingRepository(sessions).get(["Rust"], "test-model") == {}
