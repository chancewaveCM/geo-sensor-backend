"""Unit tests for notification models and schemas."""

from datetime import datetime

from app.schemas.notification import (
    AlertRuleCreate,
    AlertRuleResponse,
    NotificationConfigBase,
    NotificationConfigCreate,
    NotificationConfigResponse,
    NotificationConfigUpdate,
    NotificationLogResponse,
    NotificationTestRequest,
    ScheduleStatusResponse,
)


class TestNotificationConfigBase:
    """Tests for NotificationConfigBase schema."""

    def test_valid_config(self) -> None:
        """Test creating valid notification config."""
        config = NotificationConfigBase(
            type="webhook",
            destination="https://example.com/webhook",
            events=["run_completed", "alert_triggered"],
            is_active=True,
        )

        assert config.type == "webhook"
        assert config.destination == "https://example.com/webhook"
        assert config.events == ["run_completed", "alert_triggered"]
        assert config.is_active is True

    def test_default_values(self) -> None:
        """Test default values for optional fields."""
        config = NotificationConfigBase(
            type="email",
            destination="user@example.com",
        )

        assert config.events == []
        assert config.is_active is True
        assert config.threshold_type is None
        assert config.threshold_value is None
        assert config.comparison is None

    def test_with_alert_rule_fields(self) -> None:
        """Test config with alert rule fields."""
        config = NotificationConfigBase(
            type="webhook",
            destination="https://example.com/webhook",
            threshold_type="percentage",
            threshold_value=10.0,
            comparison="above",
        )

        assert config.threshold_type == "percentage"
        assert config.threshold_value == 10.0
        assert config.comparison == "above"


class TestNotificationConfigCreate:
    """Tests for NotificationConfigCreate schema."""

    def test_inherits_from_base(self) -> None:
        """Test that create schema inherits all base fields."""
        config = NotificationConfigCreate(
            type="email",
            destination="alert@example.com",
            events=["run_failed"],
        )

        assert hasattr(config, "type")
        assert hasattr(config, "destination")
        assert hasattr(config, "events")


class TestNotificationConfigUpdate:
    """Tests for NotificationConfigUpdate schema."""

    def test_all_fields_optional(self) -> None:
        """Test that all update fields are optional."""
        config = NotificationConfigUpdate()

        assert config.destination is None
        assert config.events is None
        assert config.is_active is None

    def test_partial_update(self) -> None:
        """Test updating only some fields."""
        config = NotificationConfigUpdate(
            is_active=False,
            events=["run_completed"],
        )

        assert config.is_active is False
        assert config.events == ["run_completed"]
        assert config.destination is None


class TestNotificationConfigResponse:
    """Tests for NotificationConfigResponse schema."""

    def test_includes_id_and_timestamps(self) -> None:
        """Test that response includes database fields."""
        now = datetime.now()

        config = NotificationConfigResponse(
            id=1,
            campaign_id=10,
            workspace_id=5,
            type="webhook",
            destination="https://example.com/webhook",
            events=["alert"],
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        assert config.id == 1
        assert config.campaign_id == 10
        assert config.workspace_id == 5
        assert config.created_at == now
        assert config.updated_at == now


class TestNotificationLogResponse:
    """Tests for NotificationLogResponse schema."""

    def test_log_response_fields(self) -> None:
        """Test notification log response schema."""
        now = datetime.now()

        log = NotificationLogResponse(
            id=1,
            notification_config_id=10,
            event_type="run_completed",
            payload='{"test": "data"}',
            status="sent",
            error_message=None,
            sent_at=now,
            created_at=now,
            updated_at=now,
        )

        assert log.id == 1
        assert log.notification_config_id == 10
        assert log.event_type == "run_completed"
        assert log.status == "sent"
        assert log.error_message is None
        assert log.sent_at == now

    def test_log_with_error(self) -> None:
        """Test log response with error message."""
        now = datetime.now()

        log = NotificationLogResponse(
            id=2,
            notification_config_id=10,
            event_type="alert_triggered",
            payload='{"alert": "data"}',
            status="failed",
            error_message="Connection timeout",
            sent_at=None,
            created_at=now,
            updated_at=now,
        )

        assert log.status == "failed"
        assert log.error_message == "Connection timeout"
        assert log.sent_at is None


class TestAlertRuleCreate:
    """Tests for AlertRuleCreate schema."""

    def test_valid_alert_rule(self) -> None:
        """Test creating valid alert rule."""
        rule = AlertRuleCreate(
            threshold_type="percentage",
            threshold_value=15.0,
            comparison="above",
        )

        assert rule.threshold_type == "percentage"
        assert rule.threshold_value == 15.0
        assert rule.comparison == "above"

    def test_absolute_threshold(self) -> None:
        """Test alert rule with absolute threshold."""
        rule = AlertRuleCreate(
            threshold_type="absolute",
            threshold_value=100.0,
            comparison="below",
        )

        assert rule.threshold_type == "absolute"
        assert rule.comparison == "below"


class TestAlertRuleResponse:
    """Tests for AlertRuleResponse schema."""

    def test_response_fields(self) -> None:
        """Test alert rule response schema."""
        response = AlertRuleResponse(
            threshold_type="percentage",
            threshold_value=10.0,
            comparison="change",
        )

        assert response.threshold_type == "percentage"
        assert response.threshold_value == 10.0
        assert response.comparison == "change"


class TestScheduleStatusResponse:
    """Tests for ScheduleStatusResponse schema."""

    def test_running_status(self) -> None:
        """Test scheduler status response."""
        status = ScheduleStatusResponse(
            status="running",
            start_time="2024-01-01T00:00:00Z",
            last_poll_time="2024-01-01T01:00:00Z",
            uptime_seconds=3600,
            total_polls=60,
            total_runs_created=5,
            errors=0,
            poll_interval_seconds=60,
        )

        assert status.status == "running"
        assert status.uptime_seconds == 3600
        assert status.total_polls == 60
        assert status.errors == 0

    def test_stopped_status(self) -> None:
        """Test stopped scheduler status."""
        status = ScheduleStatusResponse(
            status="stopped",
            start_time=None,
            last_poll_time=None,
            uptime_seconds=0,
            total_polls=0,
            total_runs_created=0,
            errors=0,
            poll_interval_seconds=60,
        )

        assert status.status == "stopped"
        assert status.start_time is None
        assert status.last_poll_time is None


class TestNotificationTestRequest:
    """Tests for NotificationTestRequest schema."""

    def test_default_test_message(self) -> None:
        """Test default test message."""
        request = NotificationTestRequest()

        assert request.test_message == "Test notification from GEO Sensor"

    def test_custom_test_message(self) -> None:
        """Test custom test message."""
        request = NotificationTestRequest(
            test_message="Custom test alert"
        )

        assert request.test_message == "Custom test alert"
