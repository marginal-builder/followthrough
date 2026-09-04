"""Background job functions for FollowThrough."""

import os
from pathlib import Path
from typing import Any

import groq

from app.core.config import settings
from app.core.db import async_session_factory
from app.models.transcript import Transcript

WHISPER_MODEL = "whisper-large-v3-turbo"


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
