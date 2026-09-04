"""Background job functions for FollowThrough."""

import logging
import os
from pathlib import Path
from typing import Any

import groq
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import settings
from app.core.db import async_session_factory
from app.models.extraction import Extraction, ExtractionResult
from app.models.transcript import Transcript

logger = logging.getLogger(__name__)

WHISPER_MODEL = "whisper-large-v3-turbo"
EXTRACTION_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """\
You are an expert meeting assistant. Given a meeting transcript, extract actionable \
tasks and decisions. Return your response as a JSON object with exactly these keys: \
"actions" (a list of objects each with "body" (string), "owner_hint" (string or null), \
and "due_date" (string or null)) and "decisions" (a list of objects each with \
"body" (string)). If there are no actions or no decisions, return an empty list for \
that key. Do not include any other text or markdown formatting."""


async def _call_llm_for_extraction(
    client: groq.AsyncGroq,
    transcript_text: str,
) -> ExtractionResult:
    """Call Groq and parse the structured extraction result."""
    response = await client.chat.completions.create(
        model=EXTRACTION_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript_text},
        ],
    )
    llm_json = response.choices[0].message.content or "{}"
    return ExtractionResult.model_validate_json(llm_json)


async def extraction_job(
    ctx: dict,
    board_id: int,
    *,
    client: groq.AsyncGroq | None = None,
    session_factory: Any = None,
) -> None:
    """Extract actions and decisions from the latest ready transcript for a board."""
    if client is None:
        client = groq.AsyncGroq(api_key=settings.GROQ_API_KEY)
    if session_factory is None:
        session_factory = async_session_factory

    async with session_factory() as session, session.begin():
        stmt = (
            select(Transcript)
            .where(Transcript.board_id == board_id, Transcript.status == "ready")
            .order_by(Transcript.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        transcript = result.scalar_one_or_none()

    if transcript is None or not transcript.text:
        return

    extraction_result: ExtractionResult | None = None
    last_error: str = ""

    for attempt in range(2):
        try:
            extraction_result = await _call_llm_for_extraction(client, transcript.text)
            break
        except ValidationError as e:
            last_error = str(e)
            continue

    async with session_factory() as session, session.begin():
        if extraction_result is not None:
            for action in extraction_result.actions:
                session.add(
                    Extraction(
                        board_id=board_id,
                        kind="action",
                        payload={
                            "body": action.body,
                            "owner_hint": action.owner_hint,
                            "due_date": action.due_date,
                        },
                        status="pending",
                    )
                )
            for decision in extraction_result.decisions:
                session.add(
                    Extraction(
                        board_id=board_id,
                        kind="decision",
                        payload={"body": decision.body},
                        status="pending",
                    )
                )
        else:
            session.add(
                Extraction(
                    board_id=board_id,
                    kind="action",
                    payload={"error": last_error},
                    status="discarded",
                )
            )


async def transcribe_recording(
    ctx: dict,
    board_id: int,
    file_path: str,
    *,
    client: groq.AsyncGroq | None = None,
    session_factory: Any = None,
) -> None:
    """Transcribe an uploaded audio recording via Groq Whisper."""
    if client is None:
        client = groq.AsyncGroq(api_key=settings.GROQ_API_KEY)
    if session_factory is None:
        session_factory = async_session_factory

    try:
        audio_path = Path(file_path)
        with open(audio_path, "rb") as audio_file:  # noqa: ASYNC230
            response = await client.audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=audio_file,
            )

        async with session_factory() as session, session.begin():
            transcript = Transcript(
                board_id=board_id,
                text=response.text,
                source="upload",
                status="ready",
            )
            session.add(transcript)
    except Exception:
        is_last_attempt = ctx.get("job_try", 1) >= ctx.get("max_tries", 1)
        if is_last_attempt:
            async with session_factory() as session, session.begin():
                transcript = Transcript(
                    board_id=board_id,
                    text=None,
                    source="upload",
                    status="failed",
                    error_message="Transcription failed after retries",
                )
                session.add(transcript)
        raise
    finally:
        if os.path.exists(file_path):
            os.unlink(file_path)

    # Trigger extraction job after successful transcription
    try:
        redis = ctx.get("redis")
        if redis is not None:
            await redis.enqueue_job("extraction_job", board_id)
    except Exception:
        logger.exception("Failed to enqueue extraction_job after transcription")
