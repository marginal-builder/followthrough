import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.templates import get_current_user
from app.models import User
from app.models.transcript import Transcript
from app.services.board_service import get_board, require_active_board

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_TEXT_LENGTH = 50_000


@router.post("/boards/{board_id}/transcripts/paste", response_class=HTMLResponse)
async def paste_transcript(
    request: Request,
    board_id: int,
    current_user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _board=Depends(require_active_board),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)

    board = await get_board(session, board_id)
    if board is None:
        return RedirectResponse(url="/boards", status_code=302)

    form = await request.form()
    text = form.get("text", "")

    if not isinstance(text, str) or not text.strip():
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Text is required")

    text = text.strip()
    if len(text) > MAX_TEXT_LENGTH:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Text too long")

    transcript = Transcript(
        board_id=board_id,
        text=text,
        source="paste",
        status="ready",
    )
    session.add(transcript)
    await session.commit()

    # Trigger extraction job (fire-and-forget, must not crash the route)
    try:
        redis_pool = request.app.state.redis_pool
        if redis_pool is not None:
            await redis_pool.enqueue_job("extraction_job", board_id)
    except Exception:
        logger.exception("Failed to enqueue extraction_job after paste")

    return HTMLResponse('<p class="text-sm text-green-600">Transcript saved</p>')
