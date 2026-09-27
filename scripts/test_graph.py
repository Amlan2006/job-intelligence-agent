"""Explicit live smoke check; uses Codex account quota and optional Groq fallback."""

import asyncio
from uuid import uuid4

import httpx

from app.config import get_settings
from app.graph.graph import build_foundation_graph
from app.llm.codex import CodexProvider
from app.llm.groq import GroqProvider
from app.llm.router import LLMRouter
from app.logging import configure_logging


async def main():
    settings = get_settings()
    configure_logging(settings.log_level)
    async with httpx.AsyncClient() as client:
        router = LLMRouter(
            CodexProvider(
                settings.codex_executable, settings.codex_model, settings.codex_timeout_seconds
            ),
            GroqProvider(
                client,
                settings.groq_api_key.get_secret_value(),
                settings.groq_model,
                settings.groq_timeout_seconds,
            ),
            timeout=settings.codex_timeout_seconds,
            fallback_timeout=settings.groq_timeout_seconds,
        )
        state = await build_foundation_graph(router).ainvoke(
            {
                "research_run_id": str(uuid4()),
                "prompt": 'Return JSON with message set to "Foundation works".',
                "errors": [],
                "warnings": [],
            }
        )
        if state.get("errors"):
            raise SystemExit(state["errors"])
        print(state["result"])


if __name__ == "__main__":
    asyncio.run(main())
