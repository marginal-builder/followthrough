"""Tests for the extraction_job background job."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.extraction import Extraction
from app.models.transcript import Transcript
from app.models.weekly_board import WeeklyBoard
from app.worker.jobs import extraction_job


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


def _make_chat_response(llm_json: str) -> AsyncMock:
    choice = MagicMock()
    choice.message.content = llm_json
    response = AsyncMock()
    response.choices = [choice]
    return response


async def _add_ready_transcript(session_factory, board_id: int, text: str, created_at=None):
    async with session_factory() as session, session.begin():
        transcript = Transcript(
            board_id=board_id,
            text=text,
            source="paste",
            status="ready",
        )
        session.add(transcript)
        await session.flush()
        if created_at is not None:
            transcript.created_at = created_at
        return transcript


async def test_valid_json_creates_pending_rows(board_id: int, test_session_factory) -> None:
    await _add_ready_transcript(test_session_factory, board_id, "Meeting notes here")

    llm_json = '{"actions": [{"body": "Do thing", "owner_hint": "Alice", "due_date": "2026-09-10"}], "decisions": [{"body": "Use Postgres"}]}'
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_make_chat_response(llm_json))

    await extraction_job({"job_try": 1}, board_id, client=mock_client, session_factory=test_session_factory)

    async with test_session_factory() as session:
        result = await session.execute(
            select(Extraction).where(Extraction.board_id == board_id).order_by(Extraction.id)
        )
        extractions = result.scalars().all()

    assert len(extractions) == 2
    action = next(e for e in extractions if e.kind == "action")
    decision = next(e for e in extractions if e.kind == "decision")
    assert action.status == "pending"
    assert action.payload["body"] == "Do thing"
    assert action.payload["owner_hint"] == "Alice"
    assert action.payload["due_date"] == "2026-09-10"
    assert decision.status == "pending"
    assert decision.payload["body"] == "Use Postgres"


async def test_retry_then_succeed(board_id: int, test_session_factory) -> None:
    await _add_ready_transcript(test_session_factory, board_id, "Meeting notes here")

    valid_json = '{"actions": [{"body": "Task A"}], "decisions": []}'

    mock_client = AsyncMock()
    err = ValidationError.from_exception_data(
        "Invalid JSON",
        line_errors=[{"loc": ("body",), "type": "json_invalid", "ctx": {"error": "parse error"}}],
    )
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[err, _make_chat_response(valid_json)]
    )

    await extraction_job({"job_try": 1}, board_id, client=mock_client, session_factory=test_session_factory)

    async with test_session_factory() as session:
        result = await session.execute(
            select(Extraction).where(Extraction.board_id == board_id)
        )
        extractions = result.scalars().all()

    assert len(extractions) == 1
    assert extractions[0].kind == "action"
    assert extractions[0].status == "pending"
    assert extractions[0].payload["body"] == "Task A"


async def test_both_calls_validation_error_creates_discarded(board_id: int, test_session_factory) -> None:
    await _add_ready_transcript(test_session_factory, board_id, "Meeting notes here")

    mock_client = AsyncMock()
    err = ValidationError.from_exception_data(
        "Invalid JSON",
        line_errors=[{"loc": ("body",), "type": "json_invalid", "ctx": {"error": "parse error"}}],
    )
    mock_client.chat.completions.create = AsyncMock(side_effect=err)

    await extraction_job({"job_try": 1}, board_id, client=mock_client, session_factory=test_session_factory)

    async with test_session_factory() as session:
        result = await session.execute(
            select(Extraction).where(Extraction.board_id == board_id)
        )
        extractions = result.scalars().all()

    assert len(extractions) == 1
    assert extractions[0].kind == "action"
    assert extractions[0].status == "discarded"
    assert "error" in extractions[0].payload


async def test_uses_latest_ready_transcript(board_id: int, test_session_factory) -> None:
    # Add two ready transcripts with different created_at
    await _add_ready_transcript(test_session_factory, board_id, "Old transcript")
    await _add_ready_transcript(test_session_factory, board_id, "New transcript")

    llm_json = '{"actions": [{"body": "From new"}], "decisions": []}'
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_make_chat_response(llm_json))

    await extraction_job({"job_try": 1}, board_id, client=mock_client, session_factory=test_session_factory)

    async with test_session_factory() as session:
        result = await session.execute(
            select(Extraction).where(Extraction.board_id == board_id)
        )
        extractions = result.scalars().all()

    assert len(extractions) == 1
    assert extractions[0].payload["body"] == "From new"


async def test_no_ready_transcript_creates_zero_extractions(board_id: int, test_session_factory) -> None:
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock()

    await extraction_job({"job_try": 1}, board_id, client=mock_client, session_factory=test_session_factory)

    async with test_session_factory() as session:
        result = await session.execute(
            select(Extraction).where(Extraction.board_id == board_id)
        )
        extractions = result.scalars().all()

    assert len(extractions) == 0
    mock_client.chat.completions.create.assert_not_called()
