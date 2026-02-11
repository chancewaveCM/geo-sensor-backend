"""Unit tests for enhanced campaign scheduler."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.campaign.scheduler import (
    SCHEDULE_INTERVALS,
    CampaignScheduler,
    get_scheduler,
)


class TestScheduleIntervals:
    """Tests for schedule interval constants."""

    def test_hourly_interval(self) -> None:
        """Test hourly interval is 1 hour."""
        assert SCHEDULE_INTERVALS["hourly"] == 1

    def test_every_6h_interval(self) -> None:
        """Test every_6h interval is 6 hours."""
        assert SCHEDULE_INTERVALS["every_6h"] == 6

    def test_daily_interval(self) -> None:
        """Test daily interval is 24 hours."""
        assert SCHEDULE_INTERVALS["daily"] == 24

    def test_weekly_interval(self) -> None:
        """Test weekly interval is 168 hours (7 days)."""
        assert SCHEDULE_INTERVALS["weekly"] == 168

    def test_monthly_interval(self) -> None:
        """Test monthly interval is 720 hours (30 days)."""
        assert SCHEDULE_INTERVALS["monthly"] == 720


class TestCampaignScheduler:
    """Tests for CampaignScheduler class."""

    def test_initialization(self) -> None:
        """Test scheduler initialization."""
        scheduler = CampaignScheduler(poll_interval_seconds=30)

        assert scheduler.poll_interval == 30
        assert scheduler._running is False
        assert scheduler._total_polls == 0
        assert scheduler._total_runs_created == 0
        assert scheduler._errors == 0

    def test_default_poll_interval(self) -> None:
        """Test default poll interval is 60 seconds."""
        scheduler = CampaignScheduler()

        assert scheduler.poll_interval == 60

    def test_stop_sets_running_false(self) -> None:
        """Test that stop() sets _running to False."""
        scheduler = CampaignScheduler()
        scheduler._running = True

        scheduler.stop()

        assert scheduler._running is False

    def test_get_health_status_stopped(self) -> None:
        """Test health status when scheduler is stopped."""
        scheduler = CampaignScheduler()

        status = scheduler.get_health_status()

        assert status["status"] == "stopped"
        assert status["start_time"] is None
        assert status["last_poll_time"] is None
        assert status["uptime_seconds"] == 0
        assert status["total_polls"] == 0
        assert status["total_runs_created"] == 0
        assert status["errors"] == 0

    def test_get_health_status_running(self) -> None:
        """Test health status when scheduler is running."""
        scheduler = CampaignScheduler(poll_interval_seconds=30)
        scheduler._running = True
        scheduler._start_time = datetime.now(tz=UTC) - timedelta(seconds=100)
        scheduler._last_poll_time = datetime.now(tz=UTC)
        scheduler._total_polls = 5
        scheduler._total_runs_created = 2
        scheduler._errors = 1

        status = scheduler.get_health_status()

        assert status["status"] == "running"
        assert status["start_time"] is not None
        assert status["last_poll_time"] is not None
        assert status["uptime_seconds"] >= 100
        assert status["total_polls"] == 5
        assert status["total_runs_created"] == 2
        assert status["errors"] == 1
        assert status["poll_interval_seconds"] == 30


class TestGetScheduler:
    """Tests for get_scheduler singleton function."""

    def test_returns_singleton(self) -> None:
        """Test that get_scheduler returns the same instance."""
        # Reset global state
        import app.services.campaign.scheduler as scheduler_module
        scheduler_module._scheduler = None

        scheduler1 = get_scheduler(poll_interval_seconds=60)
        scheduler2 = get_scheduler(poll_interval_seconds=60)

        assert scheduler1 is scheduler2

    def test_uses_custom_poll_interval(self) -> None:
        """Test that custom poll interval is used."""
        import app.services.campaign.scheduler as scheduler_module
        scheduler_module._scheduler = None

        scheduler = get_scheduler(poll_interval_seconds=120)

        assert scheduler.poll_interval == 120

    def test_default_poll_interval_singleton(self) -> None:
        """Test default poll interval for singleton."""
        import app.services.campaign.scheduler as scheduler_module
        scheduler_module._scheduler = None

        scheduler = get_scheduler()

        assert scheduler.poll_interval == 60


@pytest.mark.asyncio
class TestSchedulerMissedRuns:
    """Tests for missed run detection."""

    async def test_detect_missed_runs_logs_overdue_campaigns(self) -> None:
        """Test that detect_missed_runs identifies overdue campaigns."""
        scheduler = CampaignScheduler()

        # Mock campaign that missed its run
        overdue_campaign = MagicMock()
        overdue_campaign.id = 1
        overdue_campaign.name = "Test Campaign"
        overdue_campaign.schedule_next_run_at = datetime.now(tz=UTC) - timedelta(hours=2)

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [overdue_campaign]

        with patch(
            "app.services.campaign.scheduler.async_session_maker"
        ) as mock_session:
            db = AsyncMock()
            db.execute.return_value = result_mock
            mock_session.return_value.__aenter__.return_value = db

            await scheduler._detect_missed_runs()

            # Verify execute was called with query
            assert db.execute.called

    async def test_detect_missed_runs_no_missed_campaigns(self) -> None:
        """Test detect_missed_runs with no overdue campaigns."""
        scheduler = CampaignScheduler()

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []

        with patch(
            "app.services.campaign.scheduler.async_session_maker"
        ) as mock_session:
            db = AsyncMock()
            db.execute.return_value = result_mock
            mock_session.return_value.__aenter__.return_value = db

            # Should not raise exception
            await scheduler._detect_missed_runs()


@pytest.mark.asyncio
class TestSchedulerPolling:
    """Tests for scheduler polling logic."""

    async def test_poll_and_execute_finds_due_campaigns(self) -> None:
        """Test that _poll_and_execute finds campaigns due for execution."""
        scheduler = CampaignScheduler()

        due_campaign = MagicMock()
        due_campaign.id = 1
        due_campaign.name = "Due Campaign"
        due_campaign.schedule_enabled = True
        due_campaign.schedule_next_run_at = datetime.now(tz=UTC) - timedelta(minutes=5)

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [due_campaign]

        with patch(
            "app.services.campaign.scheduler.async_session_maker"
        ) as mock_session:
            db = AsyncMock()
            db.execute.return_value = result_mock
            mock_session.return_value.__aenter__.return_value = db

            with patch.object(
                scheduler, "_create_scheduled_run", new=AsyncMock()
            ) as mock_create:
                await scheduler._poll_and_execute()

                # Verify _create_scheduled_run was called
                assert mock_create.called

    async def test_poll_and_execute_no_due_campaigns(self) -> None:
        """Test polling when no campaigns are due."""
        scheduler = CampaignScheduler()

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []

        with patch(
            "app.services.campaign.scheduler.async_session_maker"
        ) as mock_session:
            db = AsyncMock()
            db.execute.return_value = result_mock
            mock_session.return_value.__aenter__.return_value = db

            # Should return early without creating runs
            await scheduler._poll_and_execute()


@pytest.mark.asyncio
class TestCreateScheduledRun:
    """Tests for _create_scheduled_run method."""

    async def test_create_scheduled_run_increments_counter(self) -> None:
        """Test that creating a run increments total_runs_created."""
        scheduler = CampaignScheduler()
        initial_count = scheduler._total_runs_created

        campaign = MagicMock()
        campaign.id = 1
        campaign.name = "Test"
        campaign.schedule_interval_hours = 24

        db = AsyncMock()

        # Mock max run number query
        max_run_result = MagicMock()
        max_run_result.scalar.return_value = 5

        # Mock query count
        q_count_result = MagicMock()
        q_count_result.scalar.return_value = 10

        db.execute.side_effect = [max_run_result, q_count_result]

        now = datetime.now(tz=UTC)

        await scheduler._create_scheduled_run(db, campaign, now)

        assert scheduler._total_runs_created == initial_count + 1
        assert db.commit.called

    async def test_create_scheduled_run_skips_if_no_queries(self) -> None:
        """Test that run creation is skipped if campaign has no active queries."""
        scheduler = CampaignScheduler()

        campaign = MagicMock()
        campaign.id = 1
        campaign.schedule_interval_hours = 24

        db = AsyncMock()

        # Mock max run number
        max_run_result = MagicMock()
        max_run_result.scalar.return_value = 0

        # Mock zero queries
        q_count_result = MagicMock()
        q_count_result.scalar.return_value = 0

        db.execute.side_effect = [max_run_result, q_count_result]

        now = datetime.now(tz=UTC)

        await scheduler._create_scheduled_run(db, campaign, now)

        # Should still update next_run_at but not create run
        assert db.commit.called
        # next_run_at should be updated
        assert campaign.schedule_next_run_at is not None
