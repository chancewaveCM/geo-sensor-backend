"""Background job management using asyncio.Task."""

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)


class BackgroundJobManager:
    """
    Manage background pipeline execution using asyncio.Task.

    Note: For MVP. Consider migrating to ARQ (Redis-backed) when:
    - Multiple worker processes needed
    - Job persistence across restarts required
    - Horizontal scaling required
    """

    _jobs: dict[int, asyncio.Task] = {}
    _lock = asyncio.Lock()

    @classmethod
    async def start_job(
        cls,
        job_id: int,
        coroutine: Coroutine[Any, Any, None],
    ) -> None:
        """Start a background job."""
        async with cls._lock:
            if job_id in cls._jobs and not cls._jobs[job_id].done():
                raise ValueError(f"Job {job_id} is already running")

            task = asyncio.create_task(cls._run_with_cleanup(job_id, coroutine))
            cls._jobs[job_id] = task
            logger.info(f"Started background job {job_id}")

    @classmethod
    async def _run_with_cleanup(
        cls,
        job_id: int,
        coroutine: Coroutine[Any, Any, None],
    ) -> None:
        """Run coroutine and clean up on completion."""
        try:
            await coroutine
        except asyncio.CancelledError:
            logger.info(f"Job {job_id} was cancelled")
            raise
        except Exception as e:
            logger.exception(f"Job {job_id} failed with error: {e}")
        finally:
            async with cls._lock:
                cls._jobs.pop(job_id, None)

    @classmethod
    async def cancel_job(cls, job_id: int) -> bool:
        """Cancel a running job."""
        async with cls._lock:
            if job_id in cls._jobs:
                task = cls._jobs[job_id]
                if not task.done():
                    task.cancel()
                    logger.info(f"Cancelled job {job_id}")
                    return True
        return False

    @classmethod
    def is_running(cls, job_id: int) -> bool:
        """Check if a job is currently running."""
        task = cls._jobs.get(job_id)
        return task is not None and not task.done()

    @classmethod
    def get_running_jobs(cls) -> list[int]:
        """Get list of running job IDs."""
        return [
            job_id
            for job_id, task in cls._jobs.items()
            if not task.done()
        ]
