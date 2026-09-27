# Job Intelligence Agent

Phase 1 provides FastAPI, an async LangGraph foundation workflow, a Codex CLI primary
provider, Groq fallback, Pydantic validation, structured inference logs, and PostgreSQL
models/migrations. Company research starts in Phase 2.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
codex login
docker compose up -d db
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1
```

Codex must be installed on PATH (or set `CODEX_EXECUTABLE`). The adapter runs
`codex exec` with a JSON output schema, an isolated temporary working directory,
read-only sandboxing, and ephemeral sessions. It ignores user configuration and rules
while retaining CLI authentication. An empty `CODEX_MODEL` uses the CLI default.
The CLI runs locally; OpenAI-hosted inference still requires connectivity and account
access. This is not offline model inference. See the
[official non-interactive documentation](https://developers.openai.com/codex/noninteractive).

Set `GROQ_API_KEY` and `GROQ_MODEL` to enable fallback. Timeouts, nonzero CLI exits,
empty responses, and invalid structured output trigger fallback. Both providers
failing returns a sanitized 502 response.

## Check the foundation

Open http://127.0.0.1:8000/docs or run:

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/api/v1/foundation/check \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Return a message confirming the foundation works."}'
```

`/health` checks the process; `/health/ready` checks database connectivity. Startup
and the foundation check do not require PostgreSQL, so provider tests can run
independently. Research/inference tables are prepared by Alembic; current inference
metadata is emitted as JSON logs, without prompts or raw provider errors.

## Tests

```bash
python -m pytest
ruff check .
```

Tests mock CLI subprocesses and HTTP providers; they never consume live inference
quota. They cover fallback, validation, timeouts, subprocess cleanup, cancellation,
graph/API behavior, and safe errors. PostgreSQL and live Codex smoke checks are
separate operational checks.

Run `python scripts/test_graph.py` for an explicit live Codex-to-LangGraph smoke check.
Run `python scripts/test_database.py` after migrations to verify pgvector, ORM
write/read operations, and API readiness. Test rows are rolled back.
