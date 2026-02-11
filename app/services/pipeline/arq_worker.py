"""ARQ worker for pipeline job execution."""

import logging
from datetime import UTC, datetime

from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import async_session_maker
from app.models.dead_letter import DeadLetterJob
from app.models.enums import LLMProvider, PipelineStatus
from app.models.pipeline_job import PipelineJob
from app.services.pipeline.category_generator import CategoryGeneratorService
from app.services.pipeline.orchestrator import PipelineOrchestratorService
from app.services.pipeline.query_executor import QueryExecutorService
from app.services.pipeline.query_expander import QueryExpanderService

logger = logging.getLogger(__name__)


async def run_pipeline_job(ctx: dict, job_id: int) -> None:
    """
    Execute a pipeline job.

    This is the main ARQ task function. It fetches the PipelineJob from the database,
    builds the necessary services, and runs the orchestrator.

    Args:
        ctx: ARQ context (contains Redis pool, job metadata)
        job_id: PipelineJob ID to execute
    """
    logger.info(f"ARQ worker starting job {job_id}")

    db: AsyncSession | None = None
    try:
        async with async_session_maker() as db:
            # Fetch job
            job = await db.get(PipelineJob, job_id)
            if not job:
                raise ValueError(f"PipelineJob {job_id} not found")

            # Build services for selected providers
            selected_providers = [LLMProvider(p) for p in job.llm_providers]

            category_generators = {}
            query_expanders = {}

            for provider in selected_providers:
                api_key = _get_api_key(provider)
                category_generators[provider] = CategoryGeneratorService(provider, api_key)
                query_expanders[provider] = QueryExpanderService(provider, api_key)

            query_executor = QueryExecutorService()

            # Create orchestrator with new DB session
            async with async_session_maker() as bg_db:
                orchestrator = PipelineOrchestratorService(
                    db=bg_db,
                    category_generators=category_generators,
                    query_expanders=query_expanders,
                    query_executor=query_executor,
                )

                # Determine if rerun
                is_rerun = job.status == PipelineStatus.PENDING and job.total_queries > 0

                # Execute pipeline
                await orchestrator.start_pipeline(
                    job_id=job_id,
                    company_profile_id=job.company_profile_id,
                    query_set_id=job.query_set_id,
                    is_rerun=is_rerun,
                )

        logger.info(f"ARQ worker completed job {job_id}")

    except Exception as e:
        logger.exception(f"ARQ worker failed for job {job_id}: {e}")

        # Record in dead letter queue
        async with async_session_maker() as db:
            dlq_entry = DeadLetterJob(
                job_id=job_id,
                error_message=str(e),
                retry_count=0,
                max_retries=3,
                failed_at=datetime.now(tz=UTC),
                status="failed",
            )
            db.add(dlq_entry)
            await db.commit()

        raise


def _get_api_key(provider: LLMProvider) -> str:
    """Get API key for the specified provider."""
    if provider == LLMProvider.GEMINI:
        return settings.GEMINI_API_KEY
    elif provider == LLMProvider.OPENAI:
        return settings.OPENAI_API_KEY
    else:
        raise ValueError(f"Unknown provider: {provider}")


class WorkerSettings:
    """ARQ worker settings."""

    functions = [run_pipeline_job]

    # Redis connection
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)

    # Job execution settings
    max_jobs = 5  # Max concurrent jobs
    job_timeout = 3600  # 1 hour timeout per job
    keep_result = 86400  # Keep results for 24 hours

    # Retry settings
    max_tries = 3  # Retry up to 3 times
    retry_jobs = True
    allow_abort_jobs = True

    # Worker health
    health_check_interval = 60  # Check health every 60s
    poll_delay = 0.5  # Poll for new jobs every 500ms


async def get_redis_pool():
    """Get a Redis connection pool for enqueueing jobs."""
    return await create_pool(WorkerSettings.redis_settings)
