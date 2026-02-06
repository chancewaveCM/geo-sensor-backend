"""Campaign run scheduler - DB polling approach for auto-executing scheduled campaigns."""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.models.campaign import Campaign, CampaignRun, QueryDefinition
from app.models.enums import CampaignStatus, RunStatus, TriggerType

logger = logging.getLogger(__name__)


class CampaignScheduler:
    """Polls the database for campaigns due for scheduled execution.

    Usage:
        scheduler = CampaignScheduler(poll_interval_seconds=60)
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
            "Campaign scheduler started (poll interval: %ds)",
            self.poll_interval,
        )
        while self._running:
            try:
                await self._poll_and_execute()
            except Exception:
                logger.exception("Error in scheduler poll cycle")
            await asyncio.sleep(self.poll_interval)

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        self._running = False
        logger.info("Campaign scheduler stopping...")

    async def _poll_and_execute(self) -> None:
        """Check for campaigns due for execution and create runs."""
        async with async_session_maker() as db:
            try:
                now = datetime.now(tz=UTC)

                # Find active campaigns with scheduling enabled and due for run
                result = await db.execute(
                    select(Campaign).where(
                        Campaign.status == CampaignStatus.ACTIVE.value,
                        Campaign.schedule_enabled.is_(True),
                        # Due: schedule_next_run_at is NULL or <= now
                        (Campaign.schedule_next_run_at.is_(None))
                        | (Campaign.schedule_next_run_at <= now),
                    )
                )
                due_campaigns = result.scalars().all()

                if not due_campaigns:
                    return

                logger.info("Found %d campaigns due for scheduled run", len(due_campaigns))

                for campaign in due_campaigns:
                    try:
                        await self._create_scheduled_run(db, campaign, now)
                    except Exception:
                        logger.exception(
                            "Failed to create scheduled run for campaign %d",
                            campaign.id,
                        )
                        await db.rollback()

            except Exception:
                logger.exception("Error during scheduler poll")

    async def _create_scheduled_run(
        self,
        db: AsyncSession,
        campaign: Campaign,
        now: datetime,
    ) -> None:
        """Create a scheduled CampaignRun for a due campaign."""
        # Get max run number
        max_run_result = await db.execute(
            select(func.max(CampaignRun.run_number)).where(
                CampaignRun.campaign_id == campaign.id,
            )
        )
        current_max = max_run_result.scalar() or 0
        next_run_number = current_max + 1

        # Count active queries
        q_count_result = await db.execute(
            select(func.count(QueryDefinition.id)).where(
                QueryDefinition.campaign_id == campaign.id,
                QueryDefinition.is_active.is_(True),
            )
        )
        total_queries = q_count_result.scalar() or 0

        if total_queries == 0:
            logger.warning(
                "Campaign %d has no active queries, skipping scheduled run",
                campaign.id,
            )
            # Still update next_run_at to avoid re-polling
            campaign.schedule_next_run_at = now + timedelta(
                hours=campaign.schedule_interval_hours
            )
            await db.commit()
            return

        # Default LLM providers
        default_providers = ["openai", "gemini"]

        # Create the run
        campaign_run = CampaignRun(
            campaign_id=campaign.id,
            run_number=next_run_number,
            trigger_type=TriggerType.SCHEDULED.value,
            llm_providers=json.dumps(default_providers),
            status=RunStatus.PENDING.value,
            total_queries=total_queries,
            completed_queries=0,
            failed_queries=0,
        )
        db.add(campaign_run)

        # Update next scheduled run time
        campaign.schedule_next_run_at = now + timedelta(
            hours=campaign.schedule_interval_hours
        )

        await db.commit()
        logger.info(
            "Created scheduled run #%d for campaign %d (%s), next run at %s",
            next_run_number,
            campaign.id,
            campaign.name,
            campaign.schedule_next_run_at,
        )


# Module-level singleton for easy access
_scheduler: CampaignScheduler | None = None


def get_scheduler(poll_interval_seconds: int = 60) -> CampaignScheduler:
    """Get or create the campaign scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        _scheduler = CampaignScheduler(poll_interval_seconds=poll_interval_seconds)
    return _scheduler
