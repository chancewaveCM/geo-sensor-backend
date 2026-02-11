"""Background job management using asyncio.Task or ARQ (Redis)."""

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

from arq import ArqRedis

from app.core.config import settings

logger = logging.getLogger(__name__)

# Global Redis pool (lazy-initialized)
_redis_pool: ArqRedis | None = None


class BackgroundJobManager:
    """
    Manage background pipeline execution using asyncio.Task or ARQ (Redis).

    Feature flag: settings.USE_ARQ
    - False (default): In-memory asyncio.Task (MVP mode)
    - True: Redis-backed ARQ queue (production mode)

    When USE_ARQ=True, the job is enqueued to Redis and a worker process executes it.
    When USE_ARQ=False, the job runs as an asyncio.Task in the current process.
    """

    _jobs: dict[int, asyncio.Task] = {}
    _lock = asyncio.Lock()

    @classmethod
    async def _get_redis_pool(cls) -> ArqRedis:
        """Get or create Redis pool for ARQ."""
        global _redis_pool
        if _redis_pool is None:
            from app.services.pipeline.arq_worker import get_redis_pool

            _redis_pool = await get_redis_pool()
        return _redis_pool

    @classmethod
    async def start_job(
        cls,
        job_id: int,
        coroutine: Coroutine[Any, Any, None],
    ) -> None:
        """
        Start a background job.

        If USE_ARQ=True, enqueue to Redis. Otherwise, run as asyncio.Task.
        """
        if settings.USE_ARQ:
            # ARQ mode: enqueue to Redis
            from app.services.pipeline.arq_tasks import enqueue_pipeline_job

            redis_pool = await cls._get_redis_pool()
            await enqueue_pipeline_job(redis_pool, job_id)
            logger.info(f"Enqueued job {job_id} to ARQ")
        else:
            # In-memory mode: use asyncio.Task
            async with cls._lock:
                if job_id in cls._jobs and not cls._jobs[job_id].done():
                    raise ValueError(f"Job {job_id} is already running")

                task = asyncio.create_task(cls._run_with_cleanup(job_id, coroutine))
                cls._jobs[job_id] = task
                logger.info(f"Started in-memory background job {job_id}")

    @classmethod
    async def _run_with_cleanup(
        cls,
        job_id: int,
        coroutine: Coroutine[Any, Any, None],
    ) -> None:
        """Run coroutine and clean up on completion (in-memory mode only)."""
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
        """
        Cancel a running job.

        In ARQ mode, this is a no-op (ARQ jobs can't be cancelled easily).
        In in-memory mode, cancel the asyncio.Task.
        """
        if settings.USE_ARQ:
            logger.warning(f"Cannot cancel ARQ job {job_id} (not supported)")
            return False

        async with cls._lock:
            if job_id in cls._jobs:
                task = cls._jobs[job_id]
                if not task.done():
                    task.cancel()
                    logger.info(f"Cancelled in-memory job {job_id}")
                    return True
        return False

    @classmethod
    def is_running(cls, job_id: int) -> bool:
        """
        Check if a job is currently running (in-memory mode only).

        For ARQ mode, this always returns False (use PipelineJob.status instead).
        """
        if settings.USE_ARQ:
            return False

        task = cls._jobs.get(job_id)
        return task is not None and not task.done()

    @classmethod
    def get_running_jobs(cls) -> list[int]:
        """
        Get list of running job IDs (in-memory mode only).

        For ARQ mode, returns empty list (query DB for actual status).
        """
        if settings.USE_ARQ:
            return []

        return [job_id for job_id, task in cls._jobs.items() if not task.done()]
