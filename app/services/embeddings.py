import asyncio
import json
import math
import sys
from typing import Protocol


class EmbeddingError(RuntimeError):
    pass


class EmbeddingProvider(Protocol):
    model: str

    async def embed(self, texts: list[str]) -> dict[str, list[float]]: ...


class LocalEmbeddings:
    """CPU FastEmbed in a cancellable worker; model files cached locally."""

    def __init__(self, model: str, cache_dir: str, timeout: float):
        self.model, self.cache_dir, self.timeout = model, cache_dir, timeout

    async def embed(self, texts: list[str]) -> dict[str, list[float]]:
        if not texts:
            return {}
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "app.tools.embedding_worker",
            self.model,
            self.cache_dir,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            async with asyncio.timeout(self.timeout):
                output, _ = await process.communicate(json.dumps(texts).encode())
        except BaseException:
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            await process.wait()
            raise
        try:
            result = json.loads(output)
            if process.returncode or not isinstance(result, dict):
                raise ValueError("Invalid embeddings")
            if set(result) != set(texts) or any(
                not isinstance(vector, list)
                or not 0 < len(vector) <= 4096
                or not all(
                    isinstance(value, (int, float)) and math.isfinite(value) for value in vector
                )
                for vector in result.values()
            ):
                raise ValueError("Invalid embedding shape or values")
            if len({len(vector) for vector in result.values()}) != 1:
                raise ValueError("Inconsistent embedding dimensions")
            return result
        except ValueError as exc:
            raise EmbeddingError("Local embedding model unavailable") from exc
