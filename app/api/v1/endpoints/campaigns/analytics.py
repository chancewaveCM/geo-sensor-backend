"""Campaign analytics endpoints."""

import csv
import io

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import DbSession, WorkspaceMemberDep
from app.models.insight import Insight
from app.schemas.campaign import (
    BrandRankingResponse,
    BrandSafetyMetrics,
    CampaignSummaryResponse,
    CitationShareResponse,
    GEOScoreSummaryResponse,
    InsightResponse,
    ProviderComparisonResponse,
    TimeseriesResponse,
)
from app.services.campaign.analytics import CampaignAnalyticsService
from app.services.content.insight_engine import InsightEngine

from ._common import _get_campaign_or_404

router = APIRouter()


# ---------------------------------------------------------------------------
# Analytics Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{campaign_id}/citation-share",
    response_model=CitationShareResponse,
)
async def get_citation_share(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
) -> CitationShareResponse:
    """Get citation share breakdown for a campaign."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)
    return await CampaignAnalyticsService.get_citation_share(db, campaign_id)


@router.get(
    "/{campaign_id}/timeseries",
    response_model=TimeseriesResponse,
)
async def get_campaign_timeseries(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
    brand_name: str = "target",
) -> TimeseriesResponse:
    """Get citation timeseries for a campaign."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)
    return await CampaignAnalyticsService.get_campaign_timeseries(
        db, campaign_id, brand_name
    )


@router.get(
    "/{campaign_id}/brand-ranking",
    response_model=BrandRankingResponse,
)
async def get_brand_ranking(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
) -> BrandRankingResponse:
    """Get brands ranked by citation frequency."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)
    return await CampaignAnalyticsService.get_brand_ranking(db, campaign_id)


@router.get(
    "/{campaign_id}/geo-score-summary",
    response_model=GEOScoreSummaryResponse,
)
async def get_geo_score_summary(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
) -> GEOScoreSummaryResponse:
    """Get GEO score summary (placeholder using proxy metrics)."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)
    return await CampaignAnalyticsService.get_geo_score_summary(db, campaign_id)


@router.get(
    "/{campaign_id}/provider-comparison",
    response_model=ProviderComparisonResponse,
)
async def get_provider_comparison(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
) -> ProviderComparisonResponse:
    """Get per-provider comparison metrics."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)
    return await CampaignAnalyticsService.get_provider_comparison(db, campaign_id)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


@router.get(
    "/{campaign_id}/summary",
    response_model=CampaignSummaryResponse,
)
async def get_campaign_summary(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
) -> CampaignSummaryResponse:
    """Get campaign summary with counts. Requires membership."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)
    return await CampaignAnalyticsService.get_campaign_summary(db, campaign_id)


@router.get("/{campaign_id}/export/csv")
async def export_campaign_csv(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
) -> StreamingResponse:
    """Export campaign data as CSV. Requires membership."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    # Get data from service
    data = await CampaignAnalyticsService.export_campaign_csv_data(db, campaign_id)

    # Write CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "run_number",
        "run_date",
        "llm_provider",
        "llm_model",
        "query_text",
        "cited_brand",
        "position_in_response",
        "is_target_brand",
        "confidence_score",
        "citation_span",
        "word_count",
        "citation_count",
        "latency_ms",
    ])

    for row_dict in data:
        writer.writerow([
            row_dict["run_number"],
            row_dict["run_date"],
            row_dict["llm_provider"],
            row_dict["llm_model"],
            row_dict["query_text"],
            row_dict["cited_brand"],
            row_dict["position_in_response"],
            row_dict["is_target_brand"],
            row_dict["confidence_score"],
            row_dict["citation_span"],
            row_dict["word_count"],
            row_dict["citation_count"],
            row_dict["latency_ms"],
        ])

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=campaign_{campaign_id}_export.csv"
        },
    )


@router.get(
    "/{campaign_id}/brand-safety",
    response_model=BrandSafetyMetrics,
)
async def get_brand_safety_metrics(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
) -> BrandSafetyMetrics:
    """Get brand safety risk aggregation for a campaign."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    try:
        return await CampaignAnalyticsService.get_brand_safety_metrics(db, campaign_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve brand safety metrics: {e!s}",
        )


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------


@router.get(
    "/{campaign_id}/insights",
    response_model=list[InsightResponse],
)
async def list_insights(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
    include_dismissed: bool = False,
) -> list[InsightResponse]:
    """List insights for a campaign."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    query = select(Insight).where(
        Insight.campaign_id == campaign_id,
        Insight.workspace_id == workspace_id,
    )
    if not include_dismissed:
        query = query.where(Insight.is_dismissed.is_(False))
    query = query.order_by(Insight.created_at.desc())

    result = await db.execute(query)
    insights = result.scalars().all()
    return [InsightResponse.model_validate(i) for i in insights]


@router.post(
    "/{campaign_id}/insights/generate",
    response_model=list[InsightResponse],
)
async def generate_insights(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
) -> list[InsightResponse]:
    """Generate insights by running the insight engine."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    engine = InsightEngine()
    insights = await engine.generate_insights(db, campaign_id, workspace_id)
    return [InsightResponse.model_validate(i) for i in insights]


@router.put(
    "/{campaign_id}/insights/{insight_id}/dismiss",
    response_model=InsightResponse,
)
async def dismiss_insight(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    insight_id: int,
    member: WorkspaceMemberDep,
) -> InsightResponse:
    """Dismiss an insight."""
    result = await db.execute(
        select(Insight).where(
            Insight.id == insight_id,
            Insight.campaign_id == campaign_id,
            Insight.workspace_id == workspace_id,
        )
    )
    insight = result.scalar_one_or_none()
    if insight is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insight not found",
        )
    insight.is_dismissed = True
    await db.commit()
    await db.refresh(insight)
    return InsightResponse.model_validate(insight)
