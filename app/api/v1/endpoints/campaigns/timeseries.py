"""Campaign timeseries endpoints (P1-S2)."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbSession, WorkspaceMemberDep
from app.models.annotation import CampaignAnnotation
from app.models.campaign import CampaignRun, RunResponse
from app.models.enums import RunStatus
from app.models.run_citation import RunCitation
from app.schemas.timeseries import (
    AnnotationCreate,
    AnnotationResponse,
    BrandTrend,
    EnhancedTimeseriesDataPoint,
    EnhancedTimeseriesResponse,
    TrendsSummaryResponse,
    TrendSummary,
)
from app.services.campaign.trend_detector import TrendDetector

from ._common import _get_campaign_or_404

router = APIRouter(prefix="/timeseries", tags=["campaigns-timeseries"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _build_brand_data(
    db: AsyncSession,
    campaign_id: int,
    date_from: datetime | None,
    date_to: datetime | None,
) -> dict[str, list[EnhancedTimeseriesDataPoint]]:
    """Aggregate per-brand citation data grouped by run date."""
    run_query = (
        select(CampaignRun)
        .where(
            CampaignRun.campaign_id == campaign_id,
            CampaignRun.status == RunStatus.COMPLETED.value,
        )
        .order_by(CampaignRun.run_number)
    )
    if date_from:
        run_query = run_query.where(CampaignRun.started_at >= date_from)
    if date_to:
        run_query = run_query.where(CampaignRun.started_at <= date_to)

    runs_result = await db.execute(run_query)
    runs = runs_result.scalars().all()

    brand_data: dict[str, list[EnhancedTimeseriesDataPoint]] = {}

    for run in runs:
        run_date = run.started_at or run.created_at

        # Total citations + responses for this run
        total_cit_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .where(RunResponse.campaign_run_id == run.id)
        )
        total_citations = total_cit_result.scalar() or 0

        resp_count_result = await db.execute(
            select(func.count(RunResponse.id)).where(
                RunResponse.campaign_run_id == run.id
            )
        )
        response_count = resp_count_result.scalar() or 0

        # Per-brand counts
        brand_result = await db.execute(
            select(
                RunCitation.cited_brand,
                func.count(RunCitation.id).label("count"),
            )
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .where(RunResponse.campaign_run_id == run.id)
            .group_by(RunCitation.cited_brand)
        )

        for row in brand_result:
            share = row.count / total_citations if total_citations > 0 else 0.0
            point = EnhancedTimeseriesDataPoint(
                date=run_date,
                citation_share=round(share, 4),
                citation_count=row.count,
                response_count=response_count,
            )
            brand_data.setdefault(row.cited_brand, []).append(point)

    return brand_data


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{campaign_id}/enhanced",
    response_model=EnhancedTimeseriesResponse,
)
async def get_enhanced_timeseries(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
    granularity: str = Query(default="daily", pattern="^(daily|weekly|monthly)$"),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
) -> EnhancedTimeseriesResponse:
    """Get enhanced time-series with per-brand trend data.

    Granularity currently maps to run-level aggregation (one data point per
    completed run). Future: resample to true daily/weekly/monthly buckets.
    """
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    brand_data = await _build_brand_data(db, campaign_id, date_from, date_to)

    brands: list[BrandTrend] = []
    for brand_name, points in brand_data.items():
        shares = [p.citation_share for p in points]
        direction = TrendDetector.calculate_trend(shares)

        current_share = shares[-1] if shares else 0.0
        prev_share = shares[-2] if len(shares) >= 2 else shares[0] if shares else 0.0
        change = TrendDetector.calculate_change(current_share, prev_share)

        brands.append(
            BrandTrend(
                brand_name=brand_name,
                current_share=current_share,
                trend=TrendSummary(
                    direction=direction.value,
                    change_percent=change.change_percent,
                    change_absolute=change.change_absolute,
                    period="run",
                ),
                data_points=points,
            )
        )

    # Sort by current share descending
    brands.sort(key=lambda b: b.current_share, reverse=True)

    # Determine date bounds
    all_dates = [p.date for pts in brand_data.values() for p in pts]
    actual_from = min(all_dates) if all_dates else (date_from or datetime.min)
    actual_to = max(all_dates) if all_dates else (date_to or datetime.max)

    return EnhancedTimeseriesResponse(
        campaign_id=campaign_id,
        granularity=granularity,
        date_from=actual_from,
        date_to=actual_to,
        brands=brands,
    )


@router.get(
    "/{campaign_id}/trends",
    response_model=TrendsSummaryResponse,
)
async def get_trends_summary(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
) -> TrendsSummaryResponse:
    """Get trend direction per brand (run-over-run)."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    brand_data = await _build_brand_data(db, campaign_id, None, None)

    brands: list[BrandTrend] = []
    for brand_name, points in brand_data.items():
        shares = [p.citation_share for p in points]
        direction = TrendDetector.calculate_trend(shares)

        current_share = shares[-1] if shares else 0.0
        prev_share = shares[-2] if len(shares) >= 2 else shares[0] if shares else 0.0
        change = TrendDetector.calculate_change(current_share, prev_share)

        brands.append(
            BrandTrend(
                brand_name=brand_name,
                current_share=current_share,
                trend=TrendSummary(
                    direction=direction.value,
                    change_percent=change.change_percent,
                    change_absolute=change.change_absolute,
                    period="run",
                ),
                data_points=points,
            )
        )

    brands.sort(key=lambda b: b.current_share, reverse=True)

    return TrendsSummaryResponse(campaign_id=campaign_id, brands=brands)


# ---------------------------------------------------------------------------
# Annotations CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/{campaign_id}/annotations",
    response_model=list[AnnotationResponse],
)
async def list_annotations(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
) -> list[AnnotationResponse]:
    """List annotations for a campaign."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    result = await db.execute(
        select(CampaignAnnotation)
        .where(CampaignAnnotation.campaign_id == campaign_id)
        .order_by(CampaignAnnotation.date.desc())
    )
    annotations = result.scalars().all()
    return [AnnotationResponse.model_validate(a) for a in annotations]


@router.post(
    "/{campaign_id}/annotations",
    response_model=AnnotationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_annotation(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
    body: AnnotationCreate,
) -> AnnotationResponse:
    """Create an annotation on the campaign timeseries."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    annotation = CampaignAnnotation(
        campaign_id=campaign_id,
        date=body.date,
        title=body.title,
        description=body.description,
        annotation_type=body.annotation_type,
        created_by_id=member.user_id,
    )
    db.add(annotation)
    await db.commit()
    await db.refresh(annotation)
    return AnnotationResponse.model_validate(annotation)


@router.delete(
    "/{campaign_id}/annotations/{annotation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_annotation(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    annotation_id: int,
    member: WorkspaceMemberDep,
) -> None:
    """Delete an annotation."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    result = await db.execute(
        select(CampaignAnnotation).where(
            CampaignAnnotation.id == annotation_id,
            CampaignAnnotation.campaign_id == campaign_id,
        )
    )
    annotation = result.scalar_one_or_none()
    if annotation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Annotation not found",
        )
    await db.delete(annotation)
    await db.commit()
