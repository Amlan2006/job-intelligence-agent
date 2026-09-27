import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from app.services.embeddings import EmbeddingError, LocalEmbeddings


async def test_worker_embeddings(monkeypatch):
    process = AsyncMock()
    process.returncode = 0
    process.communicate.return_value = (json.dumps({"Python": [1.0, 0.0]}).encode(), None)
    spawn = AsyncMock(return_value=process)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    result = await LocalEmbeddings("model", ".cache/embeddings", 1).embed(["Python"])
    assert result == {"Python": [1.0, 0.0]}
    assert "app.tools.embedding_worker" in spawn.call_args.args


async def test_empty_batch_skips_subprocess(monkeypatch):
    spawn = AsyncMock()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    assert await LocalEmbeddings("model", "cache", 1).embed([]) == {}
    spawn.assert_not_called()


async def test_invalid_worker_output(monkeypatch):
    process = AsyncMock()
    process.returncode = 1
    process.communicate.return_value = (b"bad", None)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    with pytest.raises(EmbeddingError):
        await LocalEmbeddings("model", "cache", 1).embed(["Python"])


async def test_timeout_kills_worker(monkeypatch):
    process = AsyncMock()
    process.returncode = None
    killed = []
    process.kill = lambda: killed.append(True)

    async def slow(*args):
        await asyncio.sleep(10)

    process.communicate.side_effect = slow
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    with pytest.raises(TimeoutError):
        await LocalEmbeddings("model", "cache", 0.01).embed(["Python"])
    assert killed
    process.wait.assert_awaited_once()


@pytest.mark.parametrize(
    "payload", [{}, {"Python": []}, {"Python": [float("nan")]}, {"Python": "not a vector"}]
)
async def test_invalid_vectors_rejected(monkeypatch, payload):
    process = AsyncMock()
    process.returncode = 0
    process.communicate.return_value = (json.dumps(payload).encode(), None)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    with pytest.raises(EmbeddingError):
        await LocalEmbeddings("model", "cache", 1).embed(["Python"])
