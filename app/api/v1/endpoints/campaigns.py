"""Campaign management endpoints."""

import csv
import io
import json

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import Float, Integer, func, select

from app.api.deps import (
    CurrentUser,
    DbSession,
    Pagination,
    WorkspaceAdminDep,
    WorkspaceMemberDep,
)
from app.models.campaign import (
    Campaign,
    CampaignCompany,
    CampaignRun,
    QueryDefinition,
    QueryVersion,
    RunResponse,
)
from app.models.company_profile import CompanyProfile
from app.models.enums import CampaignStatus, RunStatus, TriggerType
from app.models.insight import Insight
from app.models.run_citation import RunCitation
from app.schemas.campaign import (
    BrandRankingItem,
    BrandRankingResponse,
    BrandSafetyIncident,
    BrandSafetyMetrics,
    CampaignCompanyCreate,
    CampaignCompanyResponse,
    CampaignCompanyUpdate,
    CampaignCreate,
    CampaignDetailResponse,
    CampaignResponse,
    CampaignRunCreate,
    CampaignRunResponse,
    CampaignSummaryResponse,
    CampaignUpdate,
    CitationShareResponse,
    GEOScoreSummaryResponse,
    InsightResponse,
    ProviderComparisonResponse,
    ProviderMetrics,
    TimeseriesDataPoint,
    TimeseriesResponse,
)
from app.services.content.insight_engine import InsightEngine

router = APIRouter(prefix="/workspaces/{workspace_id}/campaigns", tags=["campaigns"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )
    return campaign


# ---------------------------------------------------------------------------
# Campaign CRUD
# ---------------------------------------------------------------------------


@router.post("/", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    db: DbSession,
    workspace_id: int,
    current_user: CurrentUser,
    campaign_in: CampaignCreate,
    admin: WorkspaceAdminDep,
) -> CampaignResponse:
    """Create a new campaign in the workspace. Requires ADMIN role."""
    try:
        campaign = Campaign(
            workspace_id=workspace_id,
            name=campaign_in.name,
            description=campaign_in.description,
            owner_id=current_user.id,
            schedule_interval_hours=campaign_in.schedule_interval_hours,
            schedule_enabled=campaign_in.schedule_enabled,
            status=CampaignStatus.ACTIVE.value,
        )
        db.add(campaign)
        await db.commit()
        await db.refresh(campaign)
        return CampaignResponse.model_validate(campaign)

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create campaign: {e!s}",
        )


@router.get("/", response_model=list[CampaignResponse])
async def list_campaigns(
    db: DbSession,
    workspace_id: int,
    member: WorkspaceMemberDep,
    status_filter: str | None = None,
) -> list[CampaignResponse]:
    """List campaigns in workspace. Optional ?status_filter query param."""
    query = select(Campaign).where(Campaign.workspace_id == workspace_id)
    if status_filter is not None:
        query = query.where(Campaign.status == status_filter)
    query = query.order_by(Campaign.created_at.desc())

    result = await db.execute(query)
    campaigns = result.scalars().all()
    return [CampaignResponse.model_validate(c) for c in campaigns]


@router.get("/{campaign_id}", response_model=CampaignDetailResponse)
async def get_campaign(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
) -> CampaignDetailResponse:
    """Get campaign detail with counts. Requires membership."""
    campaign = await _get_campaign_or_404(db, workspace_id, campaign_id)

    # Count queries
    q_count = await db.execute(
        select(func.count(QueryDefinition.id)).where(
            QueryDefinition.campaign_id == campaign_id,
            QueryDefinition.is_active.is_(True),
        )
    )
    query_count = q_count.scalar() or 0

    # Count runs
    r_count = await db.execute(
        select(func.count(CampaignRun.id)).where(
            CampaignRun.campaign_id == campaign_id,
        )
    )
    run_count = r_count.scalar() or 0

    # Count companies
    c_count = await db.execute(
        select(func.count(CampaignCompany.id)).where(
            CampaignCompany.campaign_id == campaign_id,
        )
    )
    company_count = c_count.scalar() or 0

    response = CampaignDetailResponse.model_validate(campaign)
    response.query_count = query_count
    response.run_count = run_count
    response.company_count = company_count
    return response


@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    campaign_in: CampaignUpdate,
    admin: WorkspaceAdminDep,
) -> CampaignResponse:
    """Update campaign. Requires ADMIN role."""
    campaign = await _get_campaign_or_404(db, workspace_id, campaign_id)

    try:
        update_data = campaign_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(campaign, field, value)

        await db.commit()
        await db.refresh(campaign)
        return CampaignResponse.model_validate(campaign)

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update campaign: {e!s}",
        )


@router.delete("/{campaign_id}", status_code=status.HTTP_200_OK)
async def delete_campaign(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    admin: WorkspaceAdminDep,
) -> dict[str, str]:
    """Soft-delete campaign (set status=archived). Requires ADMIN role."""
    campaign = await _get_campaign_or_404(db, workspace_id, campaign_id)

    try:
        campaign.status = CampaignStatus.ARCHIVED.value
        await db.commit()
        return {"message": "Campaign archived"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to archive campaign: {e!s}",
        )


# ---------------------------------------------------------------------------
# Campaign Run
# ---------------------------------------------------------------------------


@router.post(
    "/{campaign_id}/run",
    response_model=CampaignRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_campaign_run(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    run_in: CampaignRunCreate,
    member: WorkspaceMemberDep,
) -> CampaignRunResponse:
    """Create a manual campaign run. Requires membership."""
    campaign = await _get_campaign_or_404(db, workspace_id, campaign_id)

    if campaign.status != CampaignStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot run a campaign that is not active",
        )

    try:
        # Determine next run_number
        max_run = await db.execute(
            select(func.max(CampaignRun.run_number)).where(
                CampaignRun.campaign_id == campaign_id,
            )
        )
        current_max = max_run.scalar() or 0
        next_run_number = current_max + 1

        # Count active query definitions
        q_count = await db.execute(
            select(func.count(QueryDefinition.id)).where(
                QueryDefinition.campaign_id == campaign_id,
                QueryDefinition.is_active.is_(True),
            )
        )
        total_queries = q_count.scalar() or 0

        campaign_run = CampaignRun(
            campaign_id=campaign_id,
            run_number=next_run_number,
            trigger_type=TriggerType.MANUAL.value,
            llm_providers=json.dumps(run_in.llm_providers),
            status=RunStatus.PENDING.value,
            total_queries=total_queries,
            completed_queries=0,
            failed_queries=0,
        )
        db.add(campaign_run)
        await db.commit()
        await db.refresh(campaign_run)
        return CampaignRunResponse.model_validate(campaign_run)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create campaign run: {e!s}",
        )


@router.get("/{campaign_id}/runs", response_model=list[CampaignRunResponse])
async def list_campaign_runs(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
    pagination: Pagination,
) -> list[CampaignRunResponse]:
    """List campaign runs with pagination. Requires membership."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    result = await db.execute(
        select(CampaignRun)
        .where(CampaignRun.campaign_id == campaign_id)
        .order_by(CampaignRun.run_number.desc())
        .offset(pagination.skip)
        .limit(pagination.limit)
    )
    runs = result.scalars().all()
    return [CampaignRunResponse.model_validate(r) for r in runs]


@router.get(
    "/{campaign_id}/runs/{run_id}",
    response_model=CampaignRunResponse,
)
async def get_campaign_run(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    run_id: int,
    member: WorkspaceMemberDep,
) -> CampaignRunResponse:
    """Get a specific campaign run. Requires membership."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    result = await db.execute(
        select(CampaignRun).where(
            CampaignRun.id == run_id,
            CampaignRun.campaign_id == campaign_id,
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign run not found",
        )
    return CampaignRunResponse.model_validate(run)


# ---------------------------------------------------------------------------
# Campaign Company
# ---------------------------------------------------------------------------


@router.post(
    "/{campaign_id}/companies",
    response_model=CampaignCompanyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def link_campaign_company(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    current_user: CurrentUser,
    company_in: CampaignCompanyCreate,
    admin: WorkspaceAdminDep,
) -> CampaignCompanyResponse:
    """Link a company profile to the campaign. Requires ADMIN role."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    # Verify company profile exists
    cp_result = await db.execute(
        select(CompanyProfile).where(
            CompanyProfile.id == company_in.company_profile_id,
        )
    )
    company = cp_result.scalar_one_or_none()
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found",
        )

    # Check for duplicate link
    dup_result = await db.execute(
        select(CampaignCompany).where(
            CampaignCompany.campaign_id == campaign_id,
            CampaignCompany.company_profile_id == company_in.company_profile_id,
        )
    )
    if dup_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company is already linked to this campaign",
        )

    try:
        # Determine display_order
        max_order = await db.execute(
            select(func.max(CampaignCompany.display_order)).where(
                CampaignCompany.campaign_id == campaign_id,
            )
        )
        next_order = (max_order.scalar() or 0) + 1

        link = CampaignCompany(
            campaign_id=campaign_id,
            company_profile_id=company_in.company_profile_id,
            is_target_brand=company_in.is_target_brand,
            display_order=next_order,
            added_by=current_user.id,
            notes=company_in.notes,
        )
        db.add(link)
        await db.commit()
        await db.refresh(link)

        response = CampaignCompanyResponse.model_validate(link)
        response.company_name = company.name
        return response

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to link company: {e!s}",
        )


@router.get(
    "/{campaign_id}/companies",
    response_model=list[CampaignCompanyResponse],
)
async def list_campaign_companies(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
) -> list[CampaignCompanyResponse]:
    """List companies linked to the campaign. Requires membership."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    result = await db.execute(
        select(CampaignCompany)
        .where(CampaignCompany.campaign_id == campaign_id)
        .order_by(CampaignCompany.display_order)
    )
    links = result.scalars().all()

    responses = []
    for link in links:
        # Fetch company name
        cp_result = await db.execute(
            select(CompanyProfile).where(
                CompanyProfile.id == link.company_profile_id,
            )
        )
        cp = cp_result.scalar_one_or_none()

        resp = CampaignCompanyResponse.model_validate(link)
        resp.company_name = cp.name if cp else None
        responses.append(resp)

    return responses


@router.put(
    "/{campaign_id}/companies/{link_id}",
    response_model=CampaignCompanyResponse,
)
async def update_campaign_company(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    link_id: int,
    company_update: CampaignCompanyUpdate,
    admin: WorkspaceAdminDep,
) -> CampaignCompanyResponse:
    """Update campaign-company link settings. Requires ADMIN role."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    result = await db.execute(
        select(CampaignCompany).where(
            CampaignCompany.id == link_id,
            CampaignCompany.campaign_id == campaign_id,
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign-company link not found",
        )

    try:
        update_data = company_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(link, field, value)

        await db.commit()
        await db.refresh(link)

        # Fetch company name
        cp_result = await db.execute(
            select(CompanyProfile).where(
                CompanyProfile.id == link.company_profile_id,
            )
        )
        cp = cp_result.scalar_one_or_none()

        response = CampaignCompanyResponse.model_validate(link)
        response.company_name = cp.name if cp else None
        return response

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update campaign company: {e!s}",
        )


@router.delete(
    "/{campaign_id}/companies/{link_id}",
    status_code=status.HTTP_200_OK,
)
async def unlink_campaign_company(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    link_id: int,
    admin: WorkspaceAdminDep,
) -> dict[str, str]:
    """Unlink company from campaign. Requires ADMIN role."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    result = await db.execute(
        select(CampaignCompany).where(
            CampaignCompany.id == link_id,
            CampaignCompany.campaign_id == campaign_id,
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign-company link not found",
        )

    try:
        await db.delete(link)
        await db.commit()
        return {"message": "Company unlinked from campaign"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unlink company: {e!s}",
        )


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

    # Total citations count
    total_cit_result = await db.execute(
        select(func.count(RunCitation.id))
        .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .where(CampaignRun.campaign_id == campaign_id)
    )
    total_citations = total_cit_result.scalar() or 0

    # Target brand citations count
    target_cit_result = await db.execute(
        select(func.count(RunCitation.id))
        .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .where(
            CampaignRun.campaign_id == campaign_id,
            RunCitation.is_target_brand.is_(True),
        )
    )
    target_brand_citations = target_cit_result.scalar() or 0

    # Overall citation share
    overall_citation_share = (
        target_brand_citations / total_citations if total_citations > 0 else 0.0
    )

    # By provider
    by_provider_result = await db.execute(
        select(
            RunResponse.llm_provider,
            func.count(RunCitation.id).label("total"),
            func.sum(func.cast(RunCitation.is_target_brand, Integer)).label("target"),
        )
        .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .where(CampaignRun.campaign_id == campaign_id)
        .group_by(RunResponse.llm_provider)
    )
    by_provider = {}
    for row in by_provider_result:
        provider_share = row.target / row.total if row.total > 0 else 0.0
        by_provider[row.llm_provider] = provider_share

    # By brand
    by_brand_result = await db.execute(
        select(
            RunCitation.cited_brand,
            RunCitation.is_target_brand,
            func.count(RunCitation.id).label("count"),
        )
        .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .where(CampaignRun.campaign_id == campaign_id)
        .group_by(RunCitation.cited_brand, RunCitation.is_target_brand)
    )
    by_brand = []
    for row in by_brand_result:
        brand_share = row.count / total_citations if total_citations > 0 else 0.0
        by_brand.append({
            "brand": row.cited_brand,
            "share": brand_share,
            "count": row.count,
            "is_target_brand": row.is_target_brand,
        })

    return CitationShareResponse(
        campaign_id=campaign_id,
        overall_citation_share=overall_citation_share,
        total_citations=total_citations,
        target_brand_citations=target_brand_citations,
        by_provider=by_provider,
        by_brand=by_brand,
    )


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

    # Get completed runs ordered by time
    runs_result = await db.execute(
        select(CampaignRun)
        .where(
            CampaignRun.campaign_id == campaign_id,
            CampaignRun.status == RunStatus.COMPLETED.value,
        )
        .order_by(CampaignRun.run_number)
    )
    runs = runs_result.scalars().all()

    time_series = []
    for run in runs:
        # Count citations for this run
        total_cit_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .where(RunResponse.campaign_run_id == run.id)
        )
        total_citations = total_cit_result.scalar() or 0

        # Count target brand citations
        target_cit_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .where(
                RunResponse.campaign_run_id == run.id,
                RunCitation.is_target_brand.is_(True),
            )
        )
        brand_citations = target_cit_result.scalar() or 0

        citation_share_overall = (
            brand_citations / total_citations if total_citations > 0 else 0.0
        )

        # By provider for this run
        by_provider_result = await db.execute(
            select(
                RunResponse.llm_provider,
                func.count(RunCitation.id).label("total"),
                func.sum(func.cast(RunCitation.is_target_brand, Integer)).label("target"),
            )
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .where(RunResponse.campaign_run_id == run.id)
            .group_by(RunResponse.llm_provider)
        )
        citation_share_by_provider = {}
        for row in by_provider_result:
            provider_share = row.target / row.total if row.total > 0 else 0.0
            citation_share_by_provider[row.llm_provider] = provider_share

        time_series.append(
            TimeseriesDataPoint(
                run_id=run.id,
                timestamp=run.started_at or run.created_at,
                citation_share_overall=citation_share_overall,
                citation_share_by_provider=citation_share_by_provider,
                total_citations=total_citations,
                brand_citations=brand_citations,
            )
        )

    return TimeseriesResponse(
        campaign_id=campaign_id,
        brand_name=brand_name,
        time_series=time_series,
        annotations=[],
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

    # Total citations
    total_cit_result = await db.execute(
        select(func.count(RunCitation.id))
        .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .where(CampaignRun.campaign_id == campaign_id)
    )
    total_citations = total_cit_result.scalar() or 0

    # Group by brand
    brand_result = await db.execute(
        select(
            RunCitation.cited_brand,
            RunCitation.is_target_brand,
            func.count(RunCitation.id).label("count"),
        )
        .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .where(CampaignRun.campaign_id == campaign_id)
        .group_by(RunCitation.cited_brand, RunCitation.is_target_brand)
        .order_by(func.count(RunCitation.id).desc())
    )

    rankings = []
    rank = 1
    for row in brand_result:
        citation_share = row.count / total_citations if total_citations > 0 else 0.0
        rankings.append(
            BrandRankingItem(
                rank=rank,
                brand=row.cited_brand,
                citation_count=row.count,
                citation_share=citation_share,
                is_target_brand=row.is_target_brand,
            )
        )
        rank += 1

    return BrandRankingResponse(
        campaign_id=campaign_id,
        rankings=rankings,
        total_citations=total_citations,
    )


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

    # Overall proxy: avg(citation_count / word_count)
    overall_result = await db.execute(
        select(
            func.avg(
                func.cast(RunResponse.citation_count, Float) /
                func.nullif(func.cast(RunResponse.word_count, Float), 0)
            ).label("avg_geo_score"),
            func.count(RunResponse.id).label("total_runs"),
        )
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .where(
            CampaignRun.campaign_id == campaign_id,
            RunResponse.word_count.is_not(None),
            RunResponse.word_count > 0,
        )
    )
    overall_row = overall_result.one_or_none()
    avg_geo_score = overall_row.avg_geo_score or 0.0 if overall_row else 0.0
    total_runs_analyzed = overall_row.total_runs or 0 if overall_row else 0

    # By provider
    by_provider_result = await db.execute(
        select(
            RunResponse.llm_provider,
            func.avg(
                func.cast(RunResponse.citation_count, Float) /
                func.nullif(func.cast(RunResponse.word_count, Float), 0)
            ).label("avg_geo_score"),
        )
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .where(
            CampaignRun.campaign_id == campaign_id,
            RunResponse.word_count.is_not(None),
            RunResponse.word_count > 0,
        )
        .group_by(RunResponse.llm_provider)
    )
    by_provider = {}
    for row in by_provider_result:
        by_provider[row.llm_provider] = row.avg_geo_score or 0.0

    return GEOScoreSummaryResponse(
        campaign_id=campaign_id,
        avg_geo_score=avg_geo_score,
        total_runs_analyzed=total_runs_analyzed,
        by_provider=by_provider,
    )


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

    # Aggregate by provider
    provider_result = await db.execute(
        select(
            RunResponse.llm_provider,
            func.count(RunResponse.id).label("total_responses"),
            func.avg(RunResponse.word_count).label("avg_word_count"),
            func.avg(RunResponse.citation_count).label("avg_citation_count"),
            func.avg(RunResponse.latency_ms).label("avg_latency_ms"),
        )
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .where(CampaignRun.campaign_id == campaign_id)
        .group_by(RunResponse.llm_provider)
    )

    providers = []
    for row in provider_result:
        # Citation share for this provider
        target_cit_result = await db.execute(
            select(
                func.count(RunCitation.id).label("total"),
                func.sum(func.cast(RunCitation.is_target_brand, Integer)).label("target"),
            )
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                RunResponse.llm_provider == row.llm_provider,
            )
        )
        cit_row = target_cit_result.one_or_none()
        citation_share = 0.0
        if cit_row and cit_row.total and cit_row.total > 0:
            citation_share = (cit_row.target or 0) / cit_row.total

        providers.append(
            ProviderMetrics(
                provider=row.llm_provider,
                total_responses=row.total_responses,
                avg_word_count=row.avg_word_count or 0.0,
                avg_citation_count=row.avg_citation_count or 0.0,
                avg_latency_ms=row.avg_latency_ms or 0.0,
                citation_share=citation_share,
            )
        )

    return ProviderComparisonResponse(
        campaign_id=campaign_id,
        providers=providers,
    )


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

    # Total runs
    run_count_result = await db.execute(
        select(func.count(CampaignRun.id)).where(
            CampaignRun.campaign_id == campaign_id,
        )
    )
    total_runs = run_count_result.scalar() or 0

    # Total responses
    resp_count_result = await db.execute(
        select(func.count(RunResponse.id))
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .where(CampaignRun.campaign_id == campaign_id)
    )
    total_responses = resp_count_result.scalar() or 0

    # Total citations (sum of citation_count from run_responses)
    cit_sum_result = await db.execute(
        select(func.coalesce(func.sum(RunResponse.citation_count), 0))
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .where(CampaignRun.campaign_id == campaign_id)
    )
    total_citations = cit_sum_result.scalar() or 0

    # Latest run
    latest_run_result = await db.execute(
        select(CampaignRun)
        .where(CampaignRun.campaign_id == campaign_id)
        .order_by(CampaignRun.run_number.desc())
        .limit(1)
    )
    latest_run_obj = latest_run_result.scalar_one_or_none()
    latest_run = (
        CampaignRunResponse.model_validate(latest_run_obj)
        if latest_run_obj
        else None
    )

    return CampaignSummaryResponse(
        campaign_id=campaign_id,
        total_runs=total_runs,
        total_responses=total_responses,
        total_citations=total_citations,
        latest_run=latest_run,
        citation_share_by_brand={},  # Phase 4
    )


@router.get("/{campaign_id}/export/csv")
async def export_campaign_csv(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
) -> StreamingResponse:
    """Export campaign data as CSV. Requires membership."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    # Query all run responses with citations
    # Join: CampaignRun -> RunResponse -> RunCitation -> QueryVersion
    query = (
        select(
            CampaignRun.run_number,
            CampaignRun.started_at,
            RunResponse.llm_provider,
            RunResponse.llm_model,
            RunResponse.word_count,
            RunResponse.citation_count,
            RunResponse.latency_ms,
            QueryVersion.text.label("query_text"),
            RunCitation.cited_brand,
            RunCitation.position_in_response,
            RunCitation.is_target_brand,
            RunCitation.confidence_score,
            RunCitation.citation_span,
        )
        .join(RunResponse, RunResponse.campaign_run_id == CampaignRun.id)
        .join(QueryVersion, QueryVersion.id == RunResponse.query_version_id)
        .outerjoin(RunCitation, RunCitation.run_response_id == RunResponse.id)
        .where(
            CampaignRun.campaign_id == campaign_id,
            CampaignRun.status == RunStatus.COMPLETED.value,
        )
        .order_by(CampaignRun.run_number, RunResponse.llm_provider)
    )

    result = await db.execute(query)
    rows = result.all()

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

    for row in rows:
        writer.writerow([
            row.run_number,
            row.started_at.isoformat() if row.started_at else "",
            row.llm_provider,
            row.llm_model,
            row.query_text,
            row.cited_brand or "",
            row.position_in_response if row.position_in_response is not None else "",
            row.is_target_brand if row.is_target_brand is not None else "",
            row.confidence_score if row.confidence_score is not None else "",
            row.citation_span or "",
            row.word_count or "",
            row.citation_count or "",
            row.latency_ms or "",
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
        # Total citations count
        total_cit_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(CampaignRun.campaign_id == campaign_id)
        )
        total_citations = total_cit_result.scalar() or 0

        # Critical: confidence_score < 0.5
        critical_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                RunCitation.confidence_score.is_not(None),
                RunCitation.confidence_score < 0.5,
            )
        )
        critical_count = critical_result.scalar() or 0

        # Warning: 0.5 <= confidence_score < 0.7
        warning_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                RunCitation.confidence_score.is_not(None),
                RunCitation.confidence_score >= 0.5,
                RunCitation.confidence_score < 0.7,
            )
        )
        warning_count = warning_result.scalar() or 0

        # Safe: confidence_score >= 0.7
        safe_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                RunCitation.confidence_score.is_not(None),
                RunCitation.confidence_score >= 0.7,
            )
        )
        safe_count = safe_result.scalar() or 0

        # Unknown: confidence_score IS NULL
        unknown_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                RunCitation.confidence_score.is_(None),
            )
        )
        unknown_count = unknown_result.scalar() or 0

        # Verified count
        verified_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                RunCitation.is_verified.is_(True),
            )
        )
        verified_count = verified_result.scalar() or 0

        # Unverified count
        unverified_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                RunCitation.is_verified.is_(False),
            )
        )
        unverified_count = unverified_result.scalar() or 0

        # Recent incidents: last 20 citations with confidence < 0.7 OR NULL
        incidents_result = await db.execute(
            select(
                RunCitation.id,
                RunCitation.cited_brand,
                RunCitation.citation_span,
                RunCitation.confidence_score,
                RunCitation.is_verified,
                RunCitation.created_at,
                RunResponse.llm_provider,
            )
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                (
                    RunCitation.confidence_score.is_(None)
                    | (RunCitation.confidence_score < 0.7)
                ),
            )
            .order_by(RunCitation.created_at.desc())
            .limit(20)
        )
        incidents_rows = incidents_result.all()

        recent_incidents = [
            BrandSafetyIncident(
                citation_id=row.id,
                cited_brand=row.cited_brand,
                citation_span=row.citation_span,
                confidence_score=row.confidence_score,
                is_verified=row.is_verified,
                llm_provider=row.llm_provider,
                created_at=row.created_at,
            )
            for row in incidents_rows
        ]

        return BrandSafetyMetrics(
            campaign_id=campaign_id,
            total_citations=total_citations,
            critical_count=critical_count,
            warning_count=warning_count,
            safe_count=safe_count,
            unknown_count=unknown_count,
            verified_count=verified_count,
            unverified_count=unverified_count,
            recent_incidents=recent_incidents,
        )

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
