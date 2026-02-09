"""Pipeline schedule runner - DB polling approach for auto-executing scheduled pipeline reruns."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.session import async_session_maker
from app.models.enums import LLMProvider, PipelineStatus
from app.models.pipeline_job import PipelineJob
from app.models.schedule_config import ScheduleConfig
from app.services.llm.factory import LLMFactory
from app.services.pipeline.background_manager import BackgroundJobManager
from app.services.pipeline.category_generator import CategoryGeneratorService
from app.services.pipeline.orchestrator import PipelineOrchestratorService
from app.services.pipeline.query_executor import QueryExecutorService
from app.services.pipeline.query_expander import QueryExpanderService

logger = logging.getLogger(__name__)


class PipelineScheduler:
    """Polls the database for pipeline schedules due for execution.

    Usage:
        scheduler = PipelineScheduler(poll_interval_seconds=60)
        await scheduler.start()  # Runs indefinitely
        # or
        scheduler.stop()  # To stop gracefully
    """

    def __init__(self, poll_interval_seconds: int = 60):
        self.poll_interval = poll_interval_seconds
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the scheduler polling loop."""
        self._running = True
        logger.info(
            "Pipeline scheduler started (poll interval: %ds)",
            self.poll_interval,
        )
        while self._running:
            try:
                await self._poll_and_execute()
            except Exception:
                logger.exception("Error in pipeline scheduler poll cycle")
            await asyncio.sleep(self.poll_interval)

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        self._running = False
        logger.info("Pipeline scheduler stopping...")

    async def _poll_and_execute(self) -> None:
        """Check for schedules due for execution and trigger pipeline reruns."""
        async with async_session_maker() as db:
            try:
                now = datetime.now(tz=UTC)

                # Find active schedules that are due
                result = await db.execute(
                    select(ScheduleConfig)
                    .where(
                        ScheduleConfig.is_active.is_(True),
                        (ScheduleConfig.next_run_at.is_(None))
                        | (ScheduleConfig.next_run_at <= now),
                    )
                    .options(selectinload(ScheduleConfig.query_set))
                )
                due_schedules = result.scalars().all()

                if not due_schedules:
                    return

                # Only log when there are schedules to execute
                logger.info("Found %d pipeline schedules due for execution", len(due_schedules))

                for schedule in due_schedules:
                    try:
                        await self._execute_scheduled_rerun(db, schedule, now)
                    except Exception:
                        logger.exception(
                            "Failed to execute scheduled rerun for schedule %d (query_set %d)",
                            schedule.id,
                            schedule.query_set_id,
                        )
                        await db.rollback()

            except Exception:
                logger.exception("Error during pipeline scheduler poll")

    async def _execute_scheduled_rerun(
        self,
        db: AsyncSession,
        schedule: ScheduleConfig,
        now: datetime,
    ) -> None:
        """Execute a scheduled pipeline rerun."""
        query_set = schedule.query_set
        if not query_set:
            logger.warning(
                "Schedule %d has no associated query_set, skipping",
                schedule.id,
            )
            return

        # Verify ownership consistency
        if query_set.owner_id != schedule.owner_id:
            logger.error(
                "CRITICAL: Ownership mismatch detected - disabling schedule. "
                "schedule_id=%d schedule_owner=%d query_set_id=%d query_set_owner=%d",
                schedule.id,
                schedule.owner_id,
                query_set.id,
                query_set.owner_id,
            )
            schedule.is_active = False
            await db.commit()
            return

        # Create new PipelineJob for rerun
        job = PipelineJob(
            query_set_id=query_set.id,
            company_profile_id=query_set.company_profile_id,
            owner_id=schedule.owner_id,
            llm_providers=schedule.llm_providers,
            status=PipelineStatus.PENDING,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        # Build services
        def _get_api_key(provider: LLMProvider) -> str:
            if provider == LLMProvider.GEMINI:
                return settings.GEMINI_API_KEY
            elif provider == LLMProvider.OPENAI:
                return settings.OPENAI_API_KEY
            raise ValueError(f"Unknown provider: {provider}")

        try:
            providers_dict = {
                LLMProvider(p): LLMFactory.create(LLMProvider(p), _get_api_key(LLMProvider(p)))
                for p in schedule.llm_providers
            }

            category_generators = {
                provider: CategoryGeneratorService(llm)
                for provider, llm in providers_dict.items()
            }
            query_expanders = {
                provider: QueryExpanderService(llm)
                for provider, llm in providers_dict.items()
            }
            query_executor = QueryExecutorService(providers_dict)
            bg_db = async_session_maker()
            orchestrator = PipelineOrchestratorService(
                bg_db, category_generators, query_expanders, query_executor
            )

            await BackgroundJobManager.start_job(
                job.id,
                orchestrator.start_pipeline(
                    job_id=job.id,
                    company_profile_id=query_set.company_profile_id,
                    query_set_id=query_set.id,
                    is_rerun=True,
                ),
            )

            # Update schedule timestamps and reset failure count on success
            schedule.last_run_at = now
            schedule.next_run_at = now + timedelta(minutes=schedule.interval_minutes)
            schedule.failure_count = 0
            await db.commit()

            logger.info(
                "Started scheduled rerun job %d for query_set %d, next run at %s",
                job.id,
                query_set.id,
                schedule.next_run_at,
            )

        except Exception as e:
            # Log full exception with traceback
            logger.exception(
                "Failed to start scheduled rerun for schedule_id=%d query_set_id=%d",
                schedule.id,
                query_set.id,
            )

            # Mark job as failed
            job.status = PipelineStatus.FAILED
            # Only store exception type in error_message (security)
            job.error_message = f"Failed to start scheduled rerun: {type(e).__name__}"
            job.completed_at = datetime.now(tz=UTC)

            # Increment failure count
            schedule.failure_count += 1

            # Disable schedule after 3 consecutive failures
            if schedule.failure_count >= 3:
                logger.error(
                    "Schedule %d disabled after %d consecutive failures (query_set_id=%d)",
                    schedule.id,
                    schedule.failure_count,
                    query_set.id,
                )
                schedule.is_active = False
            else:
                # Still retry: update next_run_at for next poll
                schedule.next_run_at = now + timedelta(minutes=schedule.interval_minutes)
                logger.warning(
                    "Schedule %d failure count: %d/3, will retry at %s",
                    schedule.id,
                    schedule.failure_count,
                    schedule.next_run_at,
                )

            await db.commit()
            raise


# Module-level singleton for easy access
_pipeline_scheduler: PipelineScheduler | None = None


def get_pipeline_scheduler(poll_interval_seconds: int = 300) -> PipelineScheduler:
    """Get or create the pipeline scheduler singleton."""
    global _pipeline_scheduler
    if _pipeline_scheduler is None:
        _pipeline_scheduler = PipelineScheduler(poll_interval_seconds=poll_interval_seconds)
    return _pipeline_scheduler
