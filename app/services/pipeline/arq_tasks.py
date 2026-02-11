"""ARQ task helpers for enqueueing and monitoring jobs."""

import logging
from typing import Any

from arq import ArqRedis
from arq.jobs import Job

from app.models.enums import PipelineStatus

logger = logging.getLogger(__name__)


async def enqueue_pipeline_job(redis_pool: ArqRedis, job_id: int) -> Job:
    """
    Enqueue a pipeline job to ARQ.

    Args:
        redis_pool: ARQ Redis connection pool
        job_id: PipelineJob ID to execute

    Returns:
        ARQ Job object for monitoring
    """
    job = await redis_pool.enqueue_job(
        "run_pipeline_job",
        job_id,
        _job_id=f"pipeline_{job_id}",  # Unique job ID for deduplication
    )
    logger.info(f"Enqueued pipeline job {job_id} to ARQ (arq_job_id={job.job_id})")
    return job


async def get_job_status(redis_pool: ArqRedis, arq_job_id: str) -> dict[str, Any]:
    """
    Get ARQ job status.

    Args:
        redis_pool: ARQ Redis connection pool
        arq_job_id: ARQ job ID (format: "pipeline_{job_id}")

    Returns:
        Dict with job status info
    """
    job = Job(arq_job_id, redis_pool)
    info = await job.info()

    if not info:
        return {"status": "not_found", "job_id": arq_job_id}

    return {
        "job_id": arq_job_id,
        "status": info.job_status.value if info.job_status else "unknown",
        "enqueue_time": info.enqueue_time,
        "start_time": info.start_time,
        "finish_time": info.finish_time,
        "success": info.success,
        "result": info.result,
    }


def map_arq_status_to_pipeline_status(arq_status: str) -> PipelineStatus:
    """
    Map ARQ job status to PipelineStatus.

    ARQ statuses: queued, in_progress, complete, not_found
    """
    mapping = {
        "queued": PipelineStatus.PENDING,
        "deferred": PipelineStatus.PENDING,
        "in_progress": PipelineStatus.EXECUTING_QUERIES,  # Generic executing state
        "complete": PipelineStatus.COMPLETED,
        "not_found": PipelineStatus.FAILED,
    }
    return mapping.get(arq_status, PipelineStatus.FAILED)
