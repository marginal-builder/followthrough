from arq import WorkerSettings

from app.core.config import settings


class WorkerSettings(WorkerSettings):
    """ARQ worker settings."""

    redis_settings = settings.VALKEY_URL
    functions = []  # Will be populated with job functions later
    queue_name = "followthrough"
    max_jobs = 10
    job_timeout = 300
    keep_result = 3600