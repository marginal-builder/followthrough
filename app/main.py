from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.core.auth import seed_users
from app.core.templates import get_current_user, render
from app.models import User


@asynccontextmanager
async def lifespan(app: FastAPI):
    await seed_users()
    yield


app = FastAPI(
    title="FollowThrough",
    description="Team feedback and retrospective tool",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> JSONResponse:
    return JSONResponse({"status": "ok"})


from app.api.auth import router as auth_router

app.include_router(auth_router)


@app.get("/boards", response_class=HTMLResponse)
async def boards(
    request: Request,
    current_user: User | None = Depends(get_current_user),
):
    request.state.current_user = current_user
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)
    return render(
        request,
        "boards_list.html",
        {"current_user": current_user},
    )
