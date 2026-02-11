"""Campaign competitive benchmarking endpoints (P1-S3)."""

from datetime import datetime

from fastapi import APIRouter, Query

from app.api.deps import DbSession, WorkspaceMemberDep
from app.schemas.timeseries import (
    CompetitiveAlertsResponse,
    CompetitiveBrandEntry,
    CompetitiveOverviewResponse,
    CompetitiveTrendsResponse,
)
from app.services.campaign.competitive import CompetitiveAnalyzer

from ._common import _get_campaign_or_404

router = APIRouter(prefix="/competitive", tags=["campaigns-competitive"])


@router.get(
    "/{campaign_id}/overview",
    response_model=CompetitiveOverviewResponse,
)
async def get_competitive_overview(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
) -> CompetitiveOverviewResponse:
    """Get citation share matrix for all brands."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)
    return await CompetitiveAnalyzer.get_competitive_overview(db, campaign_id)


@router.get(
    "/{campaign_id}/trends",
    response_model=CompetitiveTrendsResponse,
)
async def get_competitive_trends(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
) -> CompetitiveTrendsResponse:
    """Get brand trajectories over time."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)
    return await CompetitiveAnalyzer.get_competitive_trends(
        db, campaign_id, date_from, date_to
    )


@router.get(
    "/{campaign_id}/alerts",
    response_model=CompetitiveAlertsResponse,
)
async def get_competitive_alerts(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
    threshold: float = Query(default=5.0, ge=0.1, le=100.0),
) -> CompetitiveAlertsResponse:
    """Get alerts for significant brand share changes."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)
    return await CompetitiveAnalyzer.detect_significant_changes(
        db, campaign_id, threshold
    )


@router.get(
    "/{campaign_id}/rankings",
    response_model=list[CompetitiveBrandEntry],
)
async def get_brand_rankings(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
) -> list[CompetitiveBrandEntry]:
    """Get current brand rankings by citation share (latest run)."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)
    return await CompetitiveAnalyzer.get_brand_rankings(db, campaign_id)
