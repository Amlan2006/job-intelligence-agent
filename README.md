# Job Intelligence Agent

Phase 1 provides FastAPI, an async LangGraph foundation workflow, a Codex CLI primary
provider, Groq fallback, Pydantic validation, structured inference logs, and PostgreSQL
models/migrations. Phase 2 adds company research, evidence grounding, deterministic
scoring, PostgreSQL persistence, and report retrieval.

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

Run `python -m scripts.test_graph` for an explicit live Codex-to-LangGraph smoke check.
Run `python -m scripts.test_database` after migrations to verify pgvector, ORM
write/read operations, and API readiness. Test rows are rolled back.

## Company research (Phase 2)

Apply the latest migration with `alembic upgrade head`, then use:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/research/company \
  -H 'Content-Type: application/json' \
  -d '{"company_url":"https://your-company.example"}'
```

The graph runs `research_company → score_legitimacy → generate_report`. It reads the
homepage and up to three linked about/team/careers/product/docs pages, plus up to
five search snippets. Set `TAVILY_API_KEY` for public search using the
[Tavily search API](https://docs.tavily.com/documentation/api-reference/endpoint/search).
Without the key, official-page research still runs and the report explicitly warns
that external corroboration was unavailable. Search snippets have lower confidence
than fetched pages. This is a synchronous bounded research endpoint; allow up to
`RESEARCH_TIMEOUT_SECONDS` (default 240 seconds).

Model claims must cite an existing source ID and a quote found in its text; claims
without supporting quotes are dropped. This checks quotation grounding, not whether
the quoted claim is true. Funding scoring requires the same claim on two distinct
domains. Unknown facts stay unknown. Missing facts are not negative signals.
Scores count each signal once, are bounded 0–100, and do not guarantee legitimacy.
Override individual weights using the JSON `COMPANY_SCORE_WEIGHTS` environment
variable; defaults live in `app/services/company_scoring.py`.

Reports, evidence, and inference metadata are stored transactionally. Retrieve:

- `GET /api/v1/research/{research_id}` for a specific report.
- `GET /api/v1/company/{company_id}` for the latest report.
- `GET /api/v1/company/{company_id}/evidence` for that report's evidence.

For an explicit live test, run `python -m scripts.test_company https://company-domain`.
This uses Codex quota, optionally Tavily/Groq, and saves a report in PostgreSQL.
Page fetching supports static HTML, not JavaScript-rendered pages or authenticated
sites. Private/reserved destinations and redirects to them are rejected; fetches
have size limits, timeouts, and a redirect cap. The API is intended for local use.
