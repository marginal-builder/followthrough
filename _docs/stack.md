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
| UI | Jinja2 + HTMX + Tailwind (+ Alpine.js for small client-side bits) | Click-to-edit, add-item forms, status dropdowns |
| Background jobs | arq (Redis-based) | Async-native, matches FastAPI; one pipeline only |
| Auth | fastapi-users | Email magic links (or Google OAuth); everyone can view/add, light edit control |
| File uploads | S3-compatible storage via presigned URLs | R2 / Backblaze B2 / S3; large files bypass the app server |
| AI processing | Whisper API (transcription) + structured-output LLM | Constrained by Pydantic schemas for Actions & Decisions |
| Deployment | Single container + Redis + Postgres + worker on Railway/Render | One repo |

---

## Key Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| UI approach | Jinja2 + HTMX over React | Board is click-to-edit/forms, not drag-and-drop; avoids JS tax for a Python team; single codebase |
| Job runner | arq over Celery | One pipeline (upload → transcribe → extract → write); Celery's complexity is wasted at this scale; async-native |
| Extraction safety | Pydantic-model-constrained structured output | Malformed extractions fail validation and retry instead of corrupting the board |
| Human-in-the-loop | Extractions land in "pending" state, always editable | Matches plan.md requirement ("auto-extract + always editable by humans") |
| Upload path | Presigned URLs to S3-compatible storage | Video files too large for app-server request bodies |

---

## Processing Pipeline

1. User uploads audio/video (presigned URL to storage) or pastes transcript
2. arq job: transcribe via Whisper API (skipped if transcript pasted)
3. arq job: LLM structured-output extraction → validated against Pydantic models
4. Validated Actions & Decisions written in **pending** state, linked to the week's board
5. Users review/edit → items become live board actions

Each stage retries independently.

---

## Out of Scope (inherited from plan.md)

Voting, built-in recording, auto-created boards, complex permissions, per-project boards, integrations, analytics, mobile app.

---

## Next Steps

1. Scaffold project (FastAPI + SQLModel + arq structure)
2. Data model: User, WeeklyBoard, FeedbackItem, Action, Decision, Extraction
3. Auth setup (magic links)
4. Board CRUD + HTMX interactions
5. Upload + extraction pipeline
6. History view
