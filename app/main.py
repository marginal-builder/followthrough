from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.config import settings

app = FastAPI(
    title="FollowThrough",
    description="Team feedback and retrospective tool",
    version="0.1.0",
)


@app.get("/health")
async def health_check() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({"status": "ok"})


# Placeholder for future API routes
# from app.api import boards, feedback, actions, decisions, auth
# app.include_router(boards.router)
# app.include_router(feedback.router)
# app.include_router(actions.router)
# app.include_router(decisions.router)
# app.include_router(auth.router)