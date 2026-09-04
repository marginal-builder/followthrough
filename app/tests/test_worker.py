"""Tests for the transcribe_recording background job."""

import os
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.transcript import Transcript
from app.models.weekly_board import WeeklyBoard
from app.worker.jobs import transcribe_recording


@pytest.fixture
async def board_id(engine: AsyncEngine) -> int:
    async with AsyncSession(engine) as session:
        board = WeeklyBoard(week_start=date(2026, 9, 7))
        session.add(board)
        await session.commit()
        await session.refresh(board)
        return board.id


@pytest.fixture
def test_session_factory(engine: AsyncEngine):
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
def tmp_audio(tmp_path: Path) -> Path:
    audio_file = tmp_path / "recording.wav"
    audio_file.write_bytes(b"fake-audio-content")
    return audio_file


@pytest.fixture
def mock_groq_response():
    response = AsyncMock()
    response.text = "Hello, this is the transcription."
    return response


async def test_happy_path_creates_ready_transcript(
    board_id: int, tmp_audio: Path, mock_groq_response, test_session_factory
) -> None:
    mock_client = AsyncMock()
    mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_groq_response)

    ctx = {"job_try": 1, "max_tries": 3}

    await transcribe_recording(
        ctx, board_id, str(tmp_audio), client=mock_client, session_factory=test_session_factory
    )

    async with test_session_factory() as session:
        result = await session.execute(
            select(Transcript).where(Transcript.board_id == board_id)
        )
        transcript = result.scalar_one()

    assert transcript.status == "ready"
    assert transcript.text == "Hello, this is the transcription."
    assert transcript.source == "upload"
    assert transcript.board_id == board_id
    assert not os.path.exists(tmp_audio)


async def test_failure_after_retries_creates_failed_transcript(
    board_id: int, tmp_audio: Path, test_session_factory
) -> None:
    mock_client = AsyncMock()
    mock_client.audio.transcriptions.create = AsyncMock(
        side_effect=Exception("API error")
    )

    ctx = {"job_try": 3, "max_tries": 3}

    with pytest.raises(Exception, match="API error"):
        await transcribe_recording(
            ctx, board_id, str(tmp_audio), client=mock_client, session_factory=test_session_factory
        )

    async with test_session_factory() as session:
        result = await session.execute(
            select(Transcript).where(Transcript.board_id == board_id)
        )
        transcript = result.scalar_one()

    assert transcript.status == "failed"
    assert transcript.text is None
    assert transcript.error_message == "Transcription failed after retries"
    assert not os.path.exists(tmp_audio)


async def test_failure_on_non_last_attempt_does_not_write_row(
    board_id: int, tmp_audio: Path, test_session_factory
) -> None:
    mock_client = AsyncMock()
    mock_client.audio.transcriptions.create = AsyncMock(
        side_effect=Exception("API error")
    )

    ctx = {"job_try": 1, "max_tries": 3}

    with pytest.raises(Exception, match="API error"):
        await transcribe_recording(
            ctx, board_id, str(tmp_audio), client=mock_client, session_factory=test_session_factory
        )

    async with test_session_factory() as session:
        result = await session.execute(
            select(Transcript).where(Transcript.board_id == board_id)
        )
        transcripts = result.scalars().all()

    assert len(transcripts) == 0
    assert not os.path.exists(tmp_audio)


async def test_temp_file_deleted_on_success(
    board_id: int, tmp_audio: Path, mock_groq_response, test_session_factory
) -> None:
    mock_client = AsyncMock()
    mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_groq_response)

    await transcribe_recording(
        {"job_try": 1, "max_tries": 1},
        board_id,
        str(tmp_audio),
        client=mock_client,
        session_factory=test_session_factory,
    )

    assert not os.path.exists(tmp_audio)


async def test_temp_file_deleted_on_failure(
    board_id: int, tmp_audio: Path, test_session_factory
) -> None:
    mock_client = AsyncMock()
    mock_client.audio.transcriptions.create = AsyncMock(
        side_effect=Exception("API error")
    )

    with pytest.raises(Exception, match="API error"):
        await transcribe_recording(
            {"job_try": 3, "max_tries": 3},
            board_id,
            str(tmp_audio),
            client=mock_client,
            session_factory=test_session_factory,
        )

    assert not os.path.exists(tmp_audio)
