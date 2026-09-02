# Weekly Feedback Tool – Stack Decision

**Date:** 2026-09-02  
**Status:** Decided (Option 2)

---

## Chosen Stack

**FastAPI + Jinja2/HTMX + arq + Postgres** (Python-based)

---

## Core

| Component | Choice | Notes |
|-----------|--------|-------|
| Web framework | FastAPI | Serves JSON API + Jinja2 templates from one app |
| Data layer | SQLModel + Alembic | SQLAlchemy + Pydantic combined; models double as LLM extraction contracts |
| Database | Postgres | Boards, feedback items, actions, decisions, users |
| UI | Jinja2 + HTMX 4 + Tailwind 4 (+ Alpine.js for small client-side bits) | Click-to-edit, add-item forms, status dropdowns |
| Background jobs | arq (Redis protocol, run on Valkey) | Async-native, matches FastAPI; one pipeline only; Valkey = BSD-licensed Redis fork |
| Auth | Shared team passcode + pick-your-name from seeded user list | Session cookie; no email anywhere; keeps attribution for feedback/actions |
| File uploads | Direct upload, processed in temp storage, discarded | No object storage; recordings are transcribed then deleted — nothing persisted |
| AI processing | Groq API (free tier): whisper-large-v3-turbo (transcription) + Llama structured-output LLM | One provider; constrained by Pydantic schemas for Actions & Decisions |
| Runtime | Docker Compose: app + worker + Valkey + Postgres (Python 3.14 base image) | Runs locally / on any single host; no managed deploy platform |

---

## Key Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| UI approach | Jinja2 + HTMX over React | Board is click-to-edit/forms, not drag-and-drop; avoids JS tax for a Python team; single codebase |
| Job runner | arq over Celery | One pipeline (upload → transcribe → extract → write); Celery's complexity is wasted at this scale; async-native |
| Extraction safety | Pydantic-model-constrained structured output | Malformed extractions fail validation and retry instead of corrupting the board |
| Human-in-the-loop | Extractions land in "pending" state, always editable | Matches plan.md requirement ("auto-extract + always editable by humans") |
| Auth simplicity | Team passcode + name selection over per-user accounts | Internal team of known people; no email infra, no recovery flows; spoofing names is acceptable at this trust level |
| Ephemeral recordings | Upload → temp file → transcribe → delete | MVP needs transcription, not retention; removes storage service, lifecycle rules, and privacy surface |
| AI provider | Groq free tier (whisper-large-v3-turbo + Llama) | Free, fast inference, single API key; adequate accuracy for MVP extraction |
| Deployment | Docker Compose only | Internal tool; no managed platform cost or vendor lock-in |
| Redis → Valkey | Valkey (BSD) instead of Redis (RSALv2/SSPL) | Drop-in compatible with arq; OSI license preferred |

---

## Processing Pipeline

1. User uploads audio/video (multipart, written to a temp file) or pastes transcript
2. arq job: transcribe via Groq `whisper-large-v3-turbo` (skipped if transcript pasted)
3. Temp file **deleted** — recording is never persisted
4. arq job: Groq LLM structured-output extraction → validated against Pydantic models
5. Validated Actions & Decisions written in **pending** state, linked to the week's board
6. Users review/edit → items become live board actions

Each stage retries independently.

---

## Pinned Versions (verified 2026-09-02)

| Package / Tool | Version |
|---|---|
| Python | 3.14 |
| FastAPI | 0.141.x |
| SQLModel | 0.0.42 |
| SQLAlchemy | 2.0.52 |
| Alembic | 1.19.x |
| Pydantic | 2.13.x |
| Jinja2 | 3.1.x |
| arq | 0.28.x |
| uvicorn | 0.52.x |
| HTMX | 4.x |
| Alpine.js | 3.x |
| Tailwind CSS | 4.x |
| Postgres (image) | 18 |
| Valkey (image) | 9.x |
| Docker Compose | v2+ syntax |

Exact patch versions pinned at scaffold time in `requirements.txt` / image tags.

---

## Out of Scope (inherited from plan.md)

Voting, built-in recording, auto-created boards, per-user accounts / email auth, file/recordings storage, complex permissions, per-project boards, integrations, analytics, mobile app, managed cloud deployment.

---

## Next Steps

1. Scaffold project (FastAPI + SQLModel + arq structure)
2. Data model: User, WeeklyBoard, FeedbackItem, Action, Decision, Extraction
3. Docker Compose (app, worker, Valkey, Postgres) + simple passcode auth
4. Board CRUD + HTMX interactions
5. Upload → Groq transcription/extraction pipeline (ephemeral files)
6. History view
