"""Shared dependencies and helpers for campaign endpoints."""

from sqlalchemy import select

from app.api.deps import DbSession
from app.core.exceptions import NotFoundError
from app.models.campaign import Campaign


async def _get_campaign_or_404(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
) -> Campaign:
    """Fetch campaign and verify it belongs to the workspace."""
    result = await db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.workspace_id == workspace_id,
        )
    )
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise NotFoundError("Campaign", campaign_id)
    return campaign
