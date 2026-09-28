# Job Intelligence Agent

## Luthor frontend

### Job-board-first discovery

In Discover, select **Job boards → funding check** (or send `source: "job_boards"`
to the existing discovery endpoint). Tavily searches configured public job-board
domains, reads up to ten search-result pages and follows up to ten observed job
links from those pages. Employer, role, and hiring excerpts are validated
independently against the same individual listing. Index pages are not employers.
Company websites are resolved separately: observed website links must lead to a
page naming the employer; search-only candidates also need a reciprocal link to
the original listing. Unresolved websites do not prevent funding searches, but
cannot be used to join a funding event to an employer. Research notes identify
invalid employer/role/hiring evidence, closed jobs, unreadable pages, and unresolved
websites instead of reporting simply “no jobs found.” It then
searches funding announcements for up to `JOB_BOARD_CANDIDATE_LIMIT` employers.
Companies with observed website links remain visible even if the website cannot
be verified or fetched. Website status is recorded separately as `verified`,
`unverified`, or `unreachable`. Only URLs actually observed in listing links are
retained on verification failure; guessed URLs and uncorroborated search hits are
not promoted to company websites. Unverified/unreachable websites are displayed
as `discovered` for review without automatic full company research.
Companies with verified websites remain eligible for research even when recent funding cannot
be verified (including failed funding searches). Their funding status is explicitly
`unverified`, with no invented amount/date or funding-score credit. Verified-funded
companies are researched and displayed first, followed by unverified companies.
Companies beyond the research limit remain visible as `discovered`. The original
listing becomes the job-analysis URL; website, listing, and applicable funding-source
links appear in discovery results. Old saved runs are not retroactively populated.

Configure `JOB_BOARD_DOMAINS` as a JSON list of domains in `.env`, plus
`JOB_BOARD_CANDIDATE_LIMIT` and `JOB_BOARD_TIMEOUT_SECONDS` to control cost/runtime.
This uses search-indexed public pages, not authenticated board APIs or browser
scraping. Blocked/JavaScript-only listings may be unreadable, and listing presence
does not guarantee an opening remains active. Missing funding evidence is reported
as **not verified**, never as proof that a company is unfunded. Existing strict
announcement-date and official-website evidence checks still apply.

Service destinations are configurable: the frontend requires `BACKEND_URL` in
`frontend/.env.local`; `APP_ORIGIN` optionally pins its public browser origin.
Backend provider endpoints use `GROQ_CHAT_URL`, `TAVILY_SEARCH_URL`,
`DEFILLAMA_PRO_BASE_URL`, `DEFILLAMA_PROTOCOLS_URL`, and `DEFILLAMA_RAISES_URL`.
Their defaults are centralized in settings and documented in `.env.example`.
Only configure trusted provider endpoints: requests can include API credentials.

The responsive Luthor workspace is in [`frontend/`](frontend/README.md).
Run `npm ci` and `npm run dev` from that directory, then open
http://127.0.0.1:3000. It starts in a labeled preview mode; choose **Use my
workspace** to connect to the backend described below.

Phase 1 provides FastAPI, an async LangGraph foundation workflow, a Codex CLI primary
provider, Groq fallback, Pydantic validation, structured inference logs, and PostgreSQL
models/migrations. Phase 2 adds company research, evidence grounding, deterministic
scoring, PostgreSQL persistence, and report retrieval. Phase 3 adds PDF resume
analysis, normalized profiles, and duplicate-upload reuse.
Phase 4 adds sourced job analysis, deterministic resume matching, local embeddings,
and saved opportunity reports.
Phase 5 adds source-backed public contact discovery, ranking, and saved contact snapshots.

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

## Resume analysis (Phase 3)

Install updated dependencies with `python -m pip install -e '.[dev]'` and apply
`alembic upgrade head`. Upload a PDF in Swagger's `/api/v1/resume/analyze` form, or:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/resume/analyze \
  -F 'file=@/absolute/path/to/resume.pdf;type=application/pdf'
```

The response includes `resume_id`, page count, normalized skills grouped by category,
projects, open-source contributions, employment, total experience when explicitly
stated, supporting quotes, warnings, and `cached`. Read a stored profile with
`GET /api/v1/resume/{resume_id}`. Duplicate uploads reuse the same saved profile
without parsing or calling the LLM again; PostgreSQL advisory locks serialize
concurrent duplicate uploads. Deduplication uses a SHA-256 hash of the exact PDF bytes.

PDF text extraction runs in a cancellable subprocess. Default limits are 10 MiB,
20 pages, 50,000 extracted characters, 15 seconds for parsing, and 180 seconds for
the whole analysis; environment variables in `.env.example` configure them. Scanned
or image-only files return `OCR_REQUIRED`; OCR is not implemented yet. Encrypted,
malformed, oversized PDFs receive explicit errors. Sparse resumes are supported.

Codex extracts a Pydantic-validated profile. Supporting quotes must occur in the
resume, and skills (or their known aliases) must occur in those quotes. Unsupported
items are dropped with warnings. Employment dates preserve the original wording;
unknown or unsupported dates and experience remain null. Aliases normalize naming,
such as Postgres to PostgreSQL; related technologies such as Ethereum and EVM stay
distinct. Quote checks support traceability but cannot prove every model summary
is semantically correct.

PostgreSQL stores the extracted text, filename, normalized profile, hash, and
inference metadata. The original PDF is not retained by the application. Full
resume text is sent to the configured inference provider for extraction; local
Codex CLI still uses hosted inference. Keep this unauthenticated MVP on localhost;
resume deduplication is global to this single-user database.

Run `python -m scripts.test_resume` for a synthetic end-to-end test using live Codex
and PostgreSQL, including duplicate-upload reuse. Add `--file /path/to/resume.pdf`
to test your own PDF. Normal pytest tests generate PDFs in memory and mock inference.

## Opportunity analysis (Phase 4)

Install updated dependencies, apply `alembic upgrade head`, then submit:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/opportunity/analyze \
  -H 'Content-Type: application/json' \
  -d '{"company_url":"https://company-domain", "job_url":"https://job-page", "resume_id":"SAVED-RESUME-UUID"}'
```

The graph researches and scores the company, loads the already-analyzed resume,
extracts the job, generates/caches skill embeddings, calculates a match, and saves
the report. High-risk or insufficient company evidence stops matching and returns
an explicit warning. The job URL is optional: without it the report has no job or
match score. Failed job extraction returns company research with warnings. Job
requirements and facts retain their source URL and supporting quotes.

Matching returns strong, partial, and missing requirements, relevant projects,
talking points, component scores/weights, and location/experience constraints.
It uses these default weights: required skills 50%, preferred skills 15%, project
relevance 15%, stated experience 10%, open-source relevance 10%. Components absent
from the job (preferred requirements or minimum years) are omitted and the weights
are renormalized. Missing resume projects/contributions earn zero, and unknown
experience earns zero when a minimum is stated. Scores are heuristics, not hiring
probabilities. Without supported job skill requirements, the score is null.

Exact skills and naming aliases receive full credit. Directional relationships
(such as Foundry toward Solidity) and semantic matches receive only half credit.
Semantic matches require manual review and an adjustable cosine threshold
(`SEMANTIC_MATCH_THRESHOLD`, default 0.88); this initial threshold is not calibrated
against hiring outcomes. Location and work authorization eligibility are unverified
because the current resume schema contains no user preferences or eligibility data.
Check employer-association warnings for third-party job pages.

[FastEmbed](https://qdrant.github.io/fastembed/) runs the default
`BAAI/bge-small-en-v1.5` model on local CPU. Its first run downloads the model into
`.cache/embeddings`; later runs reuse it. Embeddings are cached by text and model
in PostgreSQL using pgvector. Current matching computes cosine similarity in
Python over this small cache, rather than running a database nearest-neighbor
index. If embeddings fail/time out, exact/alias/related matching continues with
an explicit warning. Worker processes are terminated on cancellation/timeouts.

- `GET /api/v1/opportunities/{opportunity_id}` retrieves a saved report.
- `GET /api/v1/opportunities?limit=20` lists reports newest first.

`python -m scripts.test_opportunity` runs synthetic company/job pages through live
Codex, local embeddings, and PostgreSQL, using the synthetic saved resume. It tests
report retrieval and pgvector storage without relying on changing job postings.
For real pages use `--company-url URL --job-url URL --resume-id UUID`. The first
model download can take longer than the default 60-second embedding timeout;
warm the model or increase `EMBEDDING_TIMEOUT_SECONDS` if necessary. The smoke script
allows 180 seconds for that initial download.

## Contact discovery (Phase 5)

Apply `alembic upgrade head`. Opportunity analysis now includes up to 10 ranked
contacts after matching. Discovery also runs when an acceptable company has no job
URL, using the saved resume's skills; high-risk or insufficient company evidence
withholds discovery. A contact timeout returns the opportunity with a warning.

To discover contacts for a company already researched, use:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/company/COMPANY-UUID/contacts/discover \
  -H 'Content-Type: application/json' \
  -d '{"resume_id":"OPTIONAL-SAVED-RESUME-UUID"}'
```

Submit `{}` for general engineering-role ranking without resume skill overlap.
Retrieve the latest snapshot with `GET /api/v1/company/{company_id}/contacts`.
Historical opportunity reports retain their own contact lists. Older Phase 4 reports
remain readable and default to an empty contact list.

The finder reads the public homepage and up to two same-domain team/about pages,
then makes up to three Tavily searches for engineering leaders, founders, recruiters,
and public X profiles. LinkedIn pages are not fetched or authenticated. Search snippets
can identify public profiles. Without Tavily, official-page discovery still works,
but missing profiles remain null. Currently linked profiles on team pages are only
accepted when the person's source quote includes the URL or the profile itself is
a collected search-result URL; this conservative rule can reduce coverage.

Codex candidates must have supporting name/role/company evidence. Public-only company
associations are flagged as potentially outdated; official listings do not guarantee
current employment. Profile URLs are independently validated against the candidate's
source. Former-employee references, unsupported skills/URLs, and fabricated facts
are dropped. Same-name records with conflicting profile URLs remain separate with
identity warnings. No emails are guessed and no outreach is sent.

Ranking is deterministic: role relevance 30%, role-based authority 25%, exact/alias
technical overlap with resume skills 20%, company association 15%, recent activity
10%. Explicitly dated activity within 30 days earns full activity credit, within
90 days half credit, otherwise zero. Retrieval timestamps never count as activity.
These are initial heuristic weights; evidence quotes and component values explain
each result. `CONTACT_LIMIT` and `CONTACT_TIMEOUT_SECONDS` configure count/time limits.

Contacts, people/company associations, discovery snapshots, and inference metadata
are saved in PostgreSQL. Run `python -m scripts.test_contacts COMPANY-UUID` for a
live Tavily/Codex/database test; optionally add `--resume-id UUID`. Normal tests use
fixtures and mocked providers, including unsupported profiles, duplicates, former
employees, recency, ranking, workflow integration, and API behavior.

## Phase 6: personalized outreach drafts

Apply `alembic upgrade head` and restart the backend. Safe opportunity analyses now
attempt four drafts for the top-ranked contact: LinkedIn connection (up to 300
characters), LinkedIn DM, X DM and email. Missing contacts or insufficient evidence
leave outreach empty rather than inventing content. Other outreach failures return
the opportunity with a warning.

Generate a fresh set for a selected contact from a saved opportunity:

```http
POST /api/v1/outreach/generate
Content-Type: application/json

{"opportunity_id": "OPPORTUNITY-UUID", "contact_index": 0}
```

Retrieve it with `GET /api/v1/outreach/OUTREACH-UUID`. Contact indices are zero-based
and refer to the saved opportunity's contact list, not the latest discovery snapshot.
Drafts, evidence references and inference metadata are persisted atomically.

Codex selects relevant IDs from previously grounded company product/jobs/funding
quotes and resume project/skill quotes. Deterministic templates render those exact
quotes, so no unverified experience, employment duration, relationship, contact
achievement or job eligibility is asserted. This first version intentionally uses
quote-based drafts rather than unrestricted generated prose. Long quotes (over 400
characters) are excluded; unavailable suitable evidence produces a review error.
The connection note uses a shorter introduction if the resume quote will not fit.

Risky/insufficient company evidence, conflicting contact identities, missing contact
evidence and unsupported selected IDs prevent generation. Every result is `draft`
and requires manual review of factual relevance and current employment. There is no
sending integration, inferred email address or automated platform access. Resume
and public evidence supplied to Codex use hosted inference even though the CLI runs
locally. `OUTREACH_TIMEOUT_SECONDS` configures the generation timeout (default 180).
The entire opportunity still has its separate overall timeout; increase
`OPPORTUNITY_TIMEOUT_SECONDS` if a slow full workflow requires more time.

For an API/database smoke using saved company/contact research and a saved resume:
`python -m scripts.test_outreach COMPANY-UUID RESUME-UUID --local-only` uses a local
selector with no external inference. Omit `--local-only` only when permitted to send
the selected evidence to Codex; the live version also verifies inference logs.
Both modes create a labeled smoke opportunity and stored drafts but send no messages.

## Phase 7: startup discovery

Tavily is the default funding-discovery source and uses your existing `TAVILY_API_KEY`.
Apply `alembic upgrade head` and restart the backend. DefiLlama remains optional:
set `DEFILLAMA_API_KEY` and request `"source":"defillama"` to use its feed.
DefiLlama's documented
[raises endpoint requires its API plan](https://github.com/DefiLlama/api-docs/blob/main/llms-pro.txt).
Missing credentials return a saved failed report with `TAVILY_API_KEY_REQUIRED` or
`DEFILLAMA_API_KEY_REQUIRED` and HTTP 503, depending on the selected provider.

```http
POST /api/v1/discovery/run
Content-Type: application/json

{"resume_id":"RESUME-UUID","lookback_days":90,"limit":3,"categories":["DeFi"]}
```

Tavily runs three date-filtered searches and fetches up to eight distinct linked
pages. Codex extracts candidate rounds from fetched pages, then deterministic checks
require exact excerpts naming the company, funding event and explicit full event
date. Publication dates, retrieval dates and snippets alone are insufficient. USD
amounts, round labels, investors and categories must occur in the supporting quote;
missing fields stay unknown. Amounts additionally need an adjacent raise verb to
avoid confusing valuations with round sizes. Exact excerpts and inference metadata
are retained in discovery history. This is source-backed extraction, not independent
confirmation of the publisher's claims. Strict date/quote checks reduce coverage.
`FUNDING_DISCOVERY_TIMEOUT_SECONDS` bounds search/fetch/extraction (default 240).

The optional DefiLlama adapter normalizes `/api/raises` amounts from USD millions to USD, preserves
announcement dates, investors and source links, and deduplicates funding rounds.
Undisclosed amounts stay null; invalid/future/undated announcements are not treated
as recent funding. Conflicting amounts remain unknown. Category filters use exact,
case-insensitive labels; omit categories to consider all categories.

For Tavily, websites require a company-named hyperlink in the fetched announcement;
unproven websites remain unresolved. With DefiLlama, websites are resolved by ID against its public protocol registry,
or an unambiguous exact name when no ID is provided. There is no guessed website.
Companies absent from that registry appear as unresolved (up to 20 per run). You can
supply an explicit mapping and optionally a job URL:

```json
{
  "resume_id": "RESUME-UUID",
  "targets": {
    "Exact funding company name": {
      "company_url": "https://example.com",
      "job_url": "https://example.com/jobs/backend-engineer"
    }
  }
}
```

Mappings only apply to companies present in the filtered funding feed. Each resolved
company goes through the existing company research, job matching, contact and draft
workflow. Job discovery follows links from the company homepage through up to two
careers pages or supported public job boards, choosing the first plausible individual
listing. It does not search all openings for the best fit. Without a usable job,
the report retains company/contact research and leaves job matching unknown.
Existing public-URL validation applies to every fetched destination.

`GET /api/v1/discovery/runs?resume_id=RESUME-UUID` lists history;
`GET /api/v1/discovery/runs/DISCOVERY-UUID` retrieves progress and ranked results.
Each analyzed result links to its saved opportunity, which contains contacts and
any generated outreach. Runs are synchronous and can take several minutes;
`DISCOVERY_COMPANY_TIMEOUT_SECONDS` bounds each company (default 600). `limit`
bounds new analysis attempts (1–10), not cached companies. Company failures return
partial results and are retryable. Provider failures return HTTP 503. Concurrent
runs for the same resume return HTTP 409.

Ranking uses the planned weights: resume match 30, funding recency 20, exact/alias
engineering-stack overlap 15, retrieved job listing 15, engineering activity 10,
and growth 10. Funding receives full credit up to 30 days and half through 90 days;
funding-name mismatches earn no funding credit. Activity and growth currently lack
dedicated evidence collectors and remain unknown. Unknown components are reported
with evidence coverage and earn no points; weights are not redistributed, and no
evidence means a null score. This version therefore tops out at 80/100. Risky or
insufficient company evidence withholds the ranking. Scores prioritize research,
not hiring probability; a retrieved job can still be stale.

Run recurring discovery with a local worker:

```bash
source .venv/bin/activate
python -m scripts.run_discovery RESUME-UUID --watch --interval-hours 24 --limit 3
```

Omit `--watch` for one run; use `--source defillama` for the optional provider.
The worker runs only while its process is alive; no
system scheduler is installed or automatically enabled. PostgreSQL checkpoints
skip completed company/round/resume/job combinations across restarts; new rounds
and new resumes are processed again. Use `force_refresh: true` in the API to
deliberately repeat completed work. Only the most recent eligible round per company
is researched in a run. The opportunity and its checkpoint commit atomically;
interrupted runs retain saved progress and are marked partial when the next worker
acquires that resume's lock. Failed companies retry on subsequent runs.

`python -m scripts.test_discovery` tests the full graph, database, API retrieval,
locking and repeated-run deduplication using synthetic provider fixtures. It writes
labeled synthetic resume/company/opportunity records, with no external inference
or search calls. Unit/integration tests cover source errors, normalization, filters,
missing evidence, ranking, cancellation and retry behavior. Live inference follows
the existing Codex/Groq configuration; this phase does not change that configuration.
