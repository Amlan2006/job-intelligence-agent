import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.llm.base import Message
from app.llm.codex import CodexProvider
from app.llm.schemas import FoundationResult


async def test_codex_structured_response_and_usage(monkeypatch):
    captured = {}

    async def spawn(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        output = Path(args[args.index("--output-last-message") + 1])
        output.write_text('{"message":"ok"}')
        schema = Path(args[args.index("--output-schema") + 1])
        assert '"additionalProperties": false' in schema.read_text()
        process = AsyncMock()
        process.returncode = 0
        process.communicate.return_value = (
            b'{"type":"turn.completed","usage":{"input_tokens":7,"output_tokens":3}}\n',
            None,
        )
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    result = await CodexProvider().invoke([Message(role="user", content="hello")], FoundationResult)
    assert result.content == '{"message":"ok"}'
    assert (result.input_tokens, result.output_tokens) == (7, 3)
    assert "read-only" in captured["args"]
    assert captured["kwargs"]["start_new_session"]
    assert not Path(captured["args"][captured["args"].index("--cd") + 1]).exists()


async def test_codex_failure(monkeypatch):
    process = AsyncMock()
    process.returncode = 1
    process.communicate.return_value = (b"", None)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    with pytest.raises(RuntimeError, match="status 1"):
        await CodexProvider().invoke([])


async def test_codex_timeout_cleans_up(monkeypatch):
    process = AsyncMock()
    process.returncode, process.pid = None, 12345

    async def slow(*args):
        await asyncio.sleep(10)

    process.communicate.side_effect = slow
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    kill = []
    monkeypatch.setattr("app.llm.codex.os.killpg", lambda pid, sig: kill.append(pid))
    with pytest.raises(TimeoutError):
        await CodexProvider(timeout=0.01).invoke([])
    assert kill == [12345]
    process.wait.assert_awaited_once()
