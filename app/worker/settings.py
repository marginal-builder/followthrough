from typing import ClassVar

from arq import WorkerSettings

from app.core.config import settings
from app.worker.jobs import transcribe_recording


class WorkerSettings(WorkerSettings):
    """ARQ worker settings."""

    redis_settings = settings.VALKEY_URL
    functions: ClassVar[list] = [transcribe_recording]
    queue_name = "followthrough"
    max_jobs = 10
    job_timeout = 300
    keep_result = 3600