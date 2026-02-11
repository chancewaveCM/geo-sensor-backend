"""Campaign CRUD endpoints."""

import json

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

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
)
from app.models.company_profile import CompanyProfile
from app.models.enums import CampaignStatus, RunStatus, TriggerType
from app.schemas.campaign import (
    CampaignCompanyCreate,
    CampaignCompanyResponse,
    CampaignCompanyUpdate,
    CampaignCreate,
    CampaignDetailResponse,
    CampaignResponse,
    CampaignRunCreate,
    CampaignRunResponse,
    CampaignUpdate,
)

from ._common import _get_campaign_or_404

router = APIRouter()


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
