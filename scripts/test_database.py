"""Live database smoke check after `alembic upgrade head`; rolls back test rows."""

import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import LLMRun, ResearchRun
from app.db.session import create_database
from app.main import create_app


async def check_database():
    engine, _ = create_database(get_settings().database_url)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
                assert revision == "0007", f"Unexpected migration revision: {revision}"
                extension = await connection.scalar(
                    text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
                )
                assert extension, "pgvector extension missing"
                tables = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
                assert {"research_runs", "llm_runs"}.issubset(tables)
                distance = await connection.scalar(
                    text("SELECT '[1,2,3]'::vector <-> '[1,2,3]'::vector")
                )
                assert distance == 0
                async with AsyncSession(bind=connection) as session:
                    run_id = uuid4()
                    session.add(ResearchRun(id=run_id, status="test"))
                    await session.flush()
                    session.add(
                        LLMRun(
                            research_run_id=run_id,
                            metadata_json={"provider": "codex", "success": True},
                        )
                    )
                    await session.flush()
                    stored = await session.scalar(
                        select(LLMRun).where(LLMRun.research_run_id == run_id)
                    )
                    assert stored.metadata_json["provider"] == "codex"
                print(f"Migration {revision}; pgvector {extension}; ORM write/read passed")
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_database())
    with TestClient(create_app()) as client:
        response = client.get("/health/ready")
        assert response.status_code == 200, response.text
        assert response.json() == {"status": "ready"}
        print("API readiness passed; test rows rolled back")
