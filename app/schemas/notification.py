"""Notification schemas for request/response validation."""

from datetime import datetime

from pydantic import BaseModel, Field


class NotificationConfigBase(BaseModel):
    """Base notification config schema."""

    type: str = Field(..., description="Notification type: email or webhook")
    destination: str = Field(..., description="Email address or webhook URL")
    events: list[str] = Field(
        default_factory=list, description="List of events to trigger notifications"
    )
    is_active: bool = Field(default=True, description="Whether notification is active")
    threshold_type: str | None = Field(
        None, description="Alert threshold type: absolute or percentage"
    )
    threshold_value: float | None = Field(None, description="Alert threshold value")
    comparison: str | None = Field(
        None, description="Comparison operator: above, below, or change"
    )


class NotificationConfigCreate(NotificationConfigBase):
    """Schema for creating a notification config."""

    pass


class NotificationConfigUpdate(BaseModel):
    """Schema for updating a notification config."""

    destination: str | None = None
    events: list[str] | None = None
    is_active: bool | None = None
    threshold_type: str | None = None
    threshold_value: float | None = None
    comparison: str | None = None


class NotificationConfigResponse(NotificationConfigBase):
    """Schema for notification config response."""

    id: int
    campaign_id: int
    workspace_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationLogResponse(BaseModel):
    """Schema for notification log response."""

    id: int
    notification_config_id: int
    event_type: str
    payload: str
    status: str
    error_message: str | None
    sent_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AlertRuleCreate(BaseModel):
    """Schema for creating an alert rule."""

    threshold_type: str = Field(..., description="absolute or percentage")
    threshold_value: float = Field(..., description="Threshold value to trigger alert")
    comparison: str = Field(..., description="above, below, or change")


class AlertRuleResponse(BaseModel):
    """Schema for alert rule response."""

    threshold_type: str
    threshold_value: float
    comparison: str


class ScheduleStatusResponse(BaseModel):
    """Schema for scheduler health status."""

    status: str = Field(..., description="running or stopped")
    start_time: str | None = Field(None, description="ISO timestamp of scheduler start")
    last_poll_time: str | None = Field(
        None, description="ISO timestamp of last poll"
    )
    uptime_seconds: int = Field(..., description="Scheduler uptime in seconds")
    total_polls: int = Field(..., description="Total number of polls executed")
    total_runs_created: int = Field(
        ..., description="Total number of campaign runs created"
    )
    errors: int = Field(..., description="Number of errors encountered")
    poll_interval_seconds: int = Field(..., description="Polling interval in seconds")


class NotificationTestRequest(BaseModel):
    """Schema for testing a notification."""

    test_message: str = Field(
        default="Test notification from GEO Sensor",
        description="Custom test message",
    )
