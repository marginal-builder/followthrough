# FollowThrough

A team retrospective tool that captures feedback in a structured weekly board, then uses AI to extract actionable items from transcripts.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)
- A [Groq API key](https://console.groq.com) (free tier available)

## Quickstart

```bash
# 1. Clone the repo
git clone <repo-url> && cd followthrough

# 2. Copy the environment template and add your Groq API key
cp .env.example .env
# Edit .env and set GROQ_API_KEY=your-key-here

# 3. Start infrastructure (Postgres + Valkey)
docker compose up -d postgres valkey

# 4. Install Python dependencies
uv sync

# 5. Run database migrations
uv run alembic upgrade head

# 6. Seed team users (required for login)
uv run python -c "
from sqlmodel import SQLModel
from app.core.db import engine, async_session_factory
from app.models import User
import asyncio

async def seed():
    async with async_session_factory() as s:
        for name in ['Alice', 'Bob', 'Charlie']:
            s.add(User(name=name))
        await s.commit()
        print('Users created')

asyncio.run(seed())
"

# 7. Start the app (terminal 1)
uv run uvicorn app.main:app --reload

# 8. Start the background worker (terminal 2)
uv run arq app.worker.settings.WorkerSettings
```

The app is now running at `http://localhost:8000`. Log in with any seeded name and the passcode `changeme`.

## Running Tests

```bash
uv run pytest
```

Tests run against a real Postgres instance and truncate all tables between tests.

## Project Structure

```
app/
├── api/              # FastAPI route handlers
├── core/             # Config, auth, DB setup, templates
├── models/           # SQLModel database models
├── services/         # Business logic (no DB access in routes)
├── templates/        # Jinja2 templates (HTMX + Alpine.js)
├── tests/            # pytest-asyncio test suite
├── worker/           # arq background jobs (transcription, extraction)
└── main.py           # FastAPI app entry point
alembic/              # Database migrations
docker-compose.yml    # Postgres, Valkey, app, worker services
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://postgres:postgres@localhost:5432/followthrough` |
| `VALKEY_URL` | Valkey/Redis connection string | `redis://localhost:6379/0` |
| `TEAM_PASSCODE` | Passcode for team login | `changeme` |
| `SESSION_SECRET` | Secret for signing session cookies | `dev-secret-change-in-production` |
| `GROQ_API_KEY` | API key for Groq transcription/extraction | (required) |
