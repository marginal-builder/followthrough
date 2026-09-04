from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.templates import get_current_user, render
from app.models import User
from app.services import extraction_service

router = APIRouter(prefix="/boards/{board_id}")


@router.post("/extractions/{extraction_id}/approve", response_class=HTMLResponse)
async def approve_extraction(
    request: Request,
    board_id: int,
    extraction_id: int,
    current_user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)

    result = await extraction_service.approve_extraction(
        session, extraction_id, board_id
    )
    if result is None:
        return HTMLResponse("Not found", status_code=404)
    if result.get("error") == "discarded":
        return HTMLResponse("Cannot approve a discarded extraction", status_code=422)

    if result["kind"] == "action":
        return render(
            request,
            "boards/_action_item.html",
            {
                "action": result["action"],
                "owner_name": result["owner_name"],
                "board_id": board_id,
                "can_change_status": True,
            },
        )
    else:
        return render(
            request,
            "boards/_decision_item.html",
            {
                "decision": result["decision"],
                "author_name": result["author_name"],
                "board_id": board_id,
                "can_edit": True,
            },
        )


@router.post("/extractions/{extraction_id}/discard", response_class=HTMLResponse)
async def discard_extraction(
    board_id: int,
    extraction_id: int,
    current_user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)

    result = await extraction_service.discard_extraction(
        session, extraction_id, board_id
    )
    if result is None:
        return HTMLResponse("Not found", status_code=404)

    return HTMLResponse("")
