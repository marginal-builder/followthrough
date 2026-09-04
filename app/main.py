from contextlib import asynccontextmanager

from arq.connections import RedisSettings, create_pool
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.auth import seed_users
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await seed_users()
    pool = await create_pool(RedisSettings.from_dsn(settings.VALKEY_URL))
    app.state.redis_pool = pool
    yield
    await pool.aclose()


app = FastAPI(
    title="FollowThrough",
    description="Team feedback and retrospective tool",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> JSONResponse:
    return JSONResponse({"status": "ok"})


from app.api.actions import router as actions_router
from app.api.auth import router as auth_router
from app.api.boards import router as boards_router
from app.api.decisions import router as decisions_router
from app.api.extractions import router as extractions_router
from app.api.feedback import router as feedback_router
from app.api.transcripts import router as transcripts_router
from app.api.upload import router as upload_router

app.include_router(auth_router)
app.include_router(boards_router)
app.include_router(actions_router)
app.include_router(feedback_router)
app.include_router(decisions_router)
app.include_router(upload_router)
app.include_router(transcripts_router)
app.include_router(extractions_router)
