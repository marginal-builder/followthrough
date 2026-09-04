import os
import uuid
from pathlib import Path
from typing import Literal

from arq.connections import ArqRedis
from arq.jobs import Job, JobStatus
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.core.config import settings
from app.core.db import get_session
from app.core.templates import get_current_user
from app.models import User
from app.services.board_service import require_active_board

router = APIRouter()


async def enqueue_job(
    pool: ArqRedis, function: str, *args
) -> str:
    """Enqueue an arq job and return its job_id."""
    job = await pool.enqueue_job(function, *args)
    if job is None:
        raise HTTPException(status_code=500, detail="Failed to enqueue job")
    return job.job_id


async def _get_job_status(pool: ArqRedis, job_id: str) -> str:
    job = Job(job_id, pool)
    status = await job.status()
    if status is JobStatus.complete:
        result = await job.result_info()
        if result is not None and not result.success:
            return "failed"
        return "complete"
    if status is JobStatus.in_progress:
        return "running"
    if status in (JobStatus.deferred, JobStatus.queued):
        return "queued"
    return "not-found"


class _JobStatus(BaseModel):
    status: Literal["queued", "running", "complete", "failed", "not-found"]


def _processing_fragment(board_id: int, job_id: str) -> str:
    return (
        f'<div id="processing-{job_id}">'
        f'<p class="text-sm text-gray-600">Processing…</p>'
        f'<div hx-get="/boards/{board_id}/jobs/{job_id}" '
        f'hx-trigger="every 2s" hx-swap="outerHTML"></div>'
        f"</div>"
    )


def _done_fragment() -> str:
    return '<p class="text-sm text-green-600">Transcription ready</p>'


def _failed_fragment() -> str:
    return '<p class="text-sm text-red-600">Transcription failed</p>'


@router.post("/boards/{board_id}/upload", response_class=HTMLResponse)
async def upload_recording(
    request: Request,
    board_id: int,
    current_user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _board=Depends(require_active_board),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)

    form = await request.form()
    file = form.get("file")

    if not isinstance(file, StarletteUploadFile) or file.filename == "":
        raise HTTPException(status_code=400, detail="No file uploaded")

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    size = getattr(file, "size", None)
    if size is not None and size > max_bytes:
        raise HTTPException(status_code=400, detail="File too large")

    contents = await file.read()
    if len(contents) > max_bytes:
        raise HTTPException(status_code=400, detail="File too large")

    ext = Path(file.filename).suffix or ".bin"
    dest_dir = Path(settings.UPLOAD_DIR) / str(board_id)
    os.makedirs(dest_dir, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4()}{ext}"
    dest.write_bytes(contents)

    job_id = await enqueue_job(
        request.app.state.redis_pool, "transcribe_recording", board_id, str(dest)
    )
    return HTMLResponse(_processing_fragment(board_id, job_id))


@router.get("/boards/{board_id}/jobs/{job_id}")
async def get_job_status_endpoint(
    request: Request,
    board_id: int,
    job_id: str,
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)

    status = await _get_job_status(request.app.state.redis_pool, job_id)

    if request.headers.get("hx-request") == "true":
        if status == "complete":
            return HTMLResponse(_done_fragment())
        if status == "failed":
            return HTMLResponse(_failed_fragment())
        return HTMLResponse(_processing_fragment(board_id, job_id))

    return JSONResponse(_JobStatus(status=status).model_dump())
