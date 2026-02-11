"""Notification endpoints for campaign alerts and webhooks."""

import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import WorkspaceAdminDep, WorkspaceMemberDep
from app.db.session import get_db
from app.models.campaign import Campaign
from app.models.enums import NotificationStatus, NotificationType
from app.models.notification import NotificationConfig, NotificationLog
from app.schemas.notification import (
    NotificationConfigCreate,
    NotificationConfigResponse,
    NotificationConfigUpdate,
    NotificationLogResponse,
    NotificationTestRequest,
    ScheduleStatusResponse,
)
from app.services.campaign.scheduler import get_scheduler
from app.services.notification.email_sender import EmailSender
from app.services.notification.webhook_sender import WebhookSender

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/workspaces/{workspace_id}/campaigns/{campaign_id}/notifications",
    response_model=NotificationConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_notification_config(
    workspace_id: int,
    campaign_id: int,
    data: NotificationConfigCreate,
    admin: WorkspaceAdminDep,
    db: AsyncSession = Depends(get_db),
):
    """Create a notification configuration for a campaign (admin only)."""
    # Verify campaign exists and belongs to workspace
    result = await db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.workspace_id == workspace_id,
        )
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found in this workspace",
        )

    # Validate notification type
    if data.type not in [NotificationType.EMAIL.value, NotificationType.WEBHOOK.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid notification type. Must be 'email' or 'webhook'",
        )

    # Create notification config
    notification_config = NotificationConfig(
        campaign_id=campaign_id,
        workspace_id=workspace_id,
        type=data.type,
        destination=data.destination,
        events=json.dumps(data.events),
        is_active=data.is_active,
        threshold_type=data.threshold_type,
        threshold_value=data.threshold_value,
        comparison=data.comparison,
    )

    db.add(notification_config)
    await db.commit()
    await db.refresh(notification_config)

    logger.info(
        "Created notification config %d for campaign %d by user %d",
        notification_config.id,
        campaign_id,
        admin.user_id,
    )

    return notification_config


@router.get(
    "/workspaces/{workspace_id}/campaigns/{campaign_id}/notifications",
    response_model=list[NotificationConfigResponse],
)
async def list_notification_configs(
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
    db: AsyncSession = Depends(get_db),
):
    """List all notification configurations for a campaign."""
    # Verify campaign exists and belongs to workspace
    result = await db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.workspace_id == workspace_id,
        )
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found in this workspace",
        )

    # Get notification configs
    result = await db.execute(
        select(NotificationConfig).where(
            NotificationConfig.campaign_id == campaign_id,
            NotificationConfig.workspace_id == workspace_id,
        )
    )
    configs = result.scalars().all()

    return configs


@router.put(
    "/workspaces/{workspace_id}/notifications/{notification_id}",
    response_model=NotificationConfigResponse,
)
async def update_notification_config(
    workspace_id: int,
    notification_id: int,
    data: NotificationConfigUpdate,
    admin: WorkspaceAdminDep,
    db: AsyncSession = Depends(get_db),
):
    """Update a notification configuration (admin only)."""
    # Get notification config
    result = await db.execute(
        select(NotificationConfig).where(
            NotificationConfig.id == notification_id,
            NotificationConfig.workspace_id == workspace_id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification configuration not found",
        )

    # Update fields
    if data.destination is not None:
        config.destination = data.destination
    if data.events is not None:
        config.events = json.dumps(data.events)
    if data.is_active is not None:
        config.is_active = data.is_active
    if data.threshold_type is not None:
        config.threshold_type = data.threshold_type
    if data.threshold_value is not None:
        config.threshold_value = data.threshold_value
    if data.comparison is not None:
        config.comparison = data.comparison

    await db.commit()
    await db.refresh(config)

    logger.info(
        "Updated notification config %d by user %d",
        notification_id,
        admin.user_id,
    )

    return config


@router.delete(
    "/workspaces/{workspace_id}/notifications/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_notification_config(
    workspace_id: int,
    notification_id: int,
    admin: WorkspaceAdminDep,
    db: AsyncSession = Depends(get_db),
):
    """Delete a notification configuration (admin only)."""
    # Get notification config
    result = await db.execute(
        select(NotificationConfig).where(
            NotificationConfig.id == notification_id,
            NotificationConfig.workspace_id == workspace_id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification configuration not found",
        )

    await db.delete(config)
    await db.commit()

    logger.info(
        "Deleted notification config %d by user %d",
        notification_id,
        admin.user_id,
    )


@router.get(
    "/workspaces/{workspace_id}/campaigns/{campaign_id}/notifications/logs",
    response_model=list[NotificationLogResponse],
)
async def get_notification_logs(
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get notification logs for a campaign."""
    # Verify campaign exists and belongs to workspace
    result = await db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.workspace_id == workspace_id,
        )
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found in this workspace",
        )

    # Get logs via notification configs
    result = await db.execute(
        select(NotificationLog)
        .join(NotificationConfig)
        .where(
            NotificationConfig.campaign_id == campaign_id,
            NotificationConfig.workspace_id == workspace_id,
        )
        .order_by(NotificationLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()

    return logs


@router.post(
    "/workspaces/{workspace_id}/campaigns/{campaign_id}/notifications/test",
    status_code=status.HTTP_200_OK,
)
async def test_notification(
    workspace_id: int,
    campaign_id: int,
    admin: WorkspaceAdminDep,
    notification_id: int = Query(..., description="Notification config ID to test"),
    test_request: NotificationTestRequest = NotificationTestRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Test a notification configuration (admin only)."""
    # Get notification config
    result = await db.execute(
        select(NotificationConfig).where(
            NotificationConfig.id == notification_id,
            NotificationConfig.workspace_id == workspace_id,
            NotificationConfig.campaign_id == campaign_id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification configuration not found",
        )

    # Get campaign for name
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()

    # Send test notification
    success = False
    error_message = None

    if config.type == NotificationType.EMAIL.value:
        sender = EmailSender()
        success, error_message = await sender.send_campaign_alert(
            to_email=config.destination,
            campaign_name=campaign.name if campaign else "Unknown",
            event_type="test",
            details={"message": test_request.test_message},
        )
    elif config.type == NotificationType.WEBHOOK.value:
        sender = WebhookSender()
        # Validate webhook URL before sending
        try:
            sender._validate_webhook_url(config.destination)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid webhook URL: {e}"
            )
        success, error_message = await sender.send_campaign_alert(
            webhook_url=config.destination,
            campaign_id=campaign_id,
            campaign_name=campaign.name if campaign else "Unknown",
            event_type="test",
            details={"message": test_request.test_message},
        )

    # Log the test
    log = NotificationLog(
        notification_config_id=notification_id,
        event_type="test",
        payload=json.dumps({"message": test_request.test_message}),
        status=NotificationStatus.SENT.value if success else NotificationStatus.FAILED.value,
        error_message=error_message,
        sent_at=datetime.now(tz=UTC) if success else None,
    )
    db.add(log)
    await db.commit()

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test notification failed: {error_message}",
        )

    return {"message": "Test notification sent successfully", "status": "sent"}


@router.get(
    "/scheduler/status",
    response_model=ScheduleStatusResponse,
)
async def get_scheduler_status():
    """Get scheduler health status (no auth required)."""
    scheduler = get_scheduler()
    status_data = scheduler.get_health_status()
    return status_data
