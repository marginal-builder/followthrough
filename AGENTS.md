Agent Instructions — FollowThrough

Documents

- `_docs/process.md` - how work is organized

Commands

Dependencies
- `uv sync` — install/update all dependencies from `requirements.txt`
- `uv pip install <pkg>` — add a new dependency (then add to `requirements.txt`)

Running the App
- `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` — dev server (auto-reload)
- `uv run arq app.worker.settings.WorkerSettings` — background worker (arq)

Docker (full stack: app + worker + Postgres + Valkey)
- `docker compose up --build` — build & start all services
- `docker compose up` — start existing containers
- `docker compose down -v` — stop & remove volumes (clean slate)

Database (Alembic via SQLModel)
- `uv run alembic revision --autogenerate -m "message"` — create migration
- `uv run alembic upgrade head` — apply migrations
- `uv run alembic downgrade -1` — rollback last migration

Testing
- `uv run pytest` — full test suite (asyncio_mode=auto, verbose, short traceback)
- `uv run pytest app/tests/test_health.py` — single test file
- `uv run pytest -k "test_name"` — run tests matching pattern

Linting / Type Checking (when configured)
- `uv run ruff check .` — lint
- `uv run ruff check . --fix` — auto-fix lint issues
- `uv run mypy app/` — type check

---

Rules

Dependency Management
- All Python dependencies declared in `requirements.txt` (pinned versions)
- Run `uv sync` after any `requirements.txt` change
- Do not add a dependency without asking

Environment & Configuration
- App config via `app/core/config.py` (Pydantic Settings, loads from `.env`)
- Required env vars: `DATABASE_URL`, `VALKEY_URL`, `TEAM_PASSCODE`, `SESSION_SECRET`, `GROQ_API_KEY`
- `.env` is **not committed** — use `.env.example` as template
- Never hardcode secrets; always use `settings.VAR_NAME`

Database
- Models in `app/models/` using SQLModel (SQLAlchemy + Pydantic)
- All schema changes via Alembic migrations — never raw SQL DDL in code
- Run migrations before deploying or after pulling changes that include migrations

Background Jobs (arq)
- Worker settings in `app/worker/settings.py`
- Job functions registered in `WorkerSettings.functions`
- Jobs are async; use `async def` and `await` throughout
- Queue name: `followthrough` (configured in WorkerSettings)

Code Style
- Python 3.14 (target), type hints required on all public functions
- `async def` for I/O-bound work; sync `def` only for pure logic
- FastAPI route handlers return Pydantic models or `JSONResponse`
- Templates: Jinja2 in `app/templates/`, served via FastAPI `TemplateResponse`
- HTMX + Alpine.js for client-side interactions — no React/Vue

Testing
- Tests in `app/tests/` mirroring `app/` structure
- `pytest-asyncio` with `asyncio_mode = auto` (per `pytest.ini`)
- Use `httpx.AsyncClient` for API integration tests
- Fixtures in `app/tests/conftest.py` (create if needed)

Docker & Deployment
- `Dockerfile` uses `python:3.14-slim`, installs from `requirements.txt`
- `docker-compose.yml` defines 4 services: `postgres`, `valkey`, `app`, `worker`
- Volumes mount source code for hot-reload in dev
- Healthchecks on Postgres and Valkey — `depends_on: condition: service_healthy`

Git / Commits
- Conventional commit messages (e.g., `feat:`, `fix:`, `refactor:`, `chore:`)
- Run tests before committing
- Do not commit `.env`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`

Architecture Guardrails
- No direct DB access in API routes — use a service layer (`app/services/`)
- No business logic in templates — keep Jinja2 logic minimal
- Extraction pipelines (Groq) return Pydantic-validated models; invalid extractions retry
- Recordings are ephemeral: upload → transcribe → **delete temp file immediately**
- All Actions & Decisions extracted by AI land in `pending` state — human review required

---

Project Context (Quick Reference)

| Area | Location |
|------|----------|
| Entry point | `app/main.py` (FastAPI app) |
| Config | `app/core/config.py` |
| Models | `app/models/` (SQLModel) |
| API routes | `app/api/` (to be created) |
| Services | `app/services/` (to be created) |
| Background jobs | `app/worker/` (arq) |
| Templates | `app/templates/` (Jinja2 + HTMX) |
| Tests | `app/tests/` |
| Migrations | `alembic/` (to be created) |
| Docker | `Dockerfile`, `docker-compose.yml` |
| Stack decisions | `_docs/stack.md` |
| MVP scope | `_docs/plan.md` |
| Task tracking | `_docs/tasks.md` |

---

Quick Start (New Session)

```bash
# 1. Start infra
docker compose up -d postgres valkey

# 2. Install deps
uv sync

# 3. Run migrations (once alembic is set up)
uv run alembic upgrade head

# 4. Start app + worker (two terminals)
uv run uvicorn app.main:app --reload
uv run arq app.worker.settings.WorkerSettings

# 5. Run tests
uv run pytest
```