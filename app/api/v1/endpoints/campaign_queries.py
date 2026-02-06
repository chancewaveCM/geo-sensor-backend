"""Campaign query and intent cluster management endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import (
    CurrentUser,
    DbSession,
    WorkspaceAdminDep,
    WorkspaceMemberDep,
)
from app.models.campaign import (
    Campaign,
    IntentCluster,
    QueryDefinition,
    QueryVersion,
)
from app.models.enums import QueryType
from app.schemas.campaign import (
    IntentClusterCreate,
    IntentClusterResponse,
    IntentClusterUpdate,
    QueryDefinitionCreate,
    QueryDefinitionResponse,
    QueryVersionCreate,
    QueryVersionResponse,
)

router = APIRouter(
    prefix="/workspaces/{workspace_id}/campaigns/{campaign_id}",
    tags=["campaign-queries"],
)


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
# Intent Clusters
# ---------------------------------------------------------------------------


@router.post(
    "/clusters",
    response_model=IntentClusterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_intent_cluster(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    cluster_in: IntentClusterCreate,
    admin: WorkspaceAdminDep,
) -> IntentClusterResponse:
    """Create an intent cluster. Requires ADMIN role."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    try:
        cluster = IntentCluster(
            campaign_id=campaign_id,
            name=cluster_in.name,
            description=cluster_in.description,
            order_index=cluster_in.order_index,
        )
        db.add(cluster)
        await db.commit()
        await db.refresh(cluster)
        return IntentClusterResponse.model_validate(cluster)

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create intent cluster: {e!s}",
        )


@router.get("/clusters", response_model=list[IntentClusterResponse])
async def list_intent_clusters(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
) -> list[IntentClusterResponse]:
    """List intent clusters for a campaign. Requires membership."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    result = await db.execute(
        select(IntentCluster)
        .where(IntentCluster.campaign_id == campaign_id)
        .order_by(IntentCluster.order_index)
    )
    clusters = result.scalars().all()
    return [IntentClusterResponse.model_validate(c) for c in clusters]


@router.put(
    "/clusters/{cluster_id}",
    response_model=IntentClusterResponse,
)
async def update_intent_cluster(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    cluster_id: int,
    cluster_in: IntentClusterUpdate,
    admin: WorkspaceAdminDep,
) -> IntentClusterResponse:
    """Update an intent cluster. Requires ADMIN role."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    result = await db.execute(
        select(IntentCluster).where(
            IntentCluster.id == cluster_id,
            IntentCluster.campaign_id == campaign_id,
        )
    )
    cluster = result.scalar_one_or_none()
    if cluster is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Intent cluster not found",
        )

    try:
        update_data = cluster_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(cluster, field, value)

        await db.commit()
        await db.refresh(cluster)
        return IntentClusterResponse.model_validate(cluster)

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update intent cluster: {e!s}",
        )


# ---------------------------------------------------------------------------
# Query Definitions
# ---------------------------------------------------------------------------


@router.post(
    "/queries",
    response_model=QueryDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_query_definition(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    current_user: CurrentUser,
    query_in: QueryDefinitionCreate,
    member: WorkspaceMemberDep,
) -> QueryDefinitionResponse:
    """Create a query definition with initial version v1.

    Anchor queries require ADMIN role; exploration queries require MEMBER.
    """
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    # Anchor queries require ADMIN
    if query_in.query_type == QueryType.ANCHOR.value:
        if member.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can create anchor queries",
            )

    # Validate intent_cluster belongs to this campaign if provided
    if query_in.intent_cluster_id is not None:
        ic_result = await db.execute(
            select(IntentCluster).where(
                IntentCluster.id == query_in.intent_cluster_id,
                IntentCluster.campaign_id == campaign_id,
            )
        )
        if ic_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Intent cluster not found in this campaign",
            )

    try:
        # Create QueryDefinition
        query_def = QueryDefinition(
            campaign_id=campaign_id,
            intent_cluster_id=query_in.intent_cluster_id,
            query_type=query_in.query_type,
            current_version=1,
            is_active=True,
            is_retired=False,
            created_by=current_user.id,
        )
        db.add(query_def)
        await db.flush()  # Get query_def.id

        # Create initial QueryVersion (v1)
        query_version = QueryVersion(
            query_definition_id=query_def.id,
            version=1,
            text=query_in.text,
            persona_type=query_in.persona_type,
            change_reason="Initial version",
            changed_by=current_user.id,
            is_current=True,
            effective_from=datetime.now(tz=UTC),
        )
        db.add(query_version)

        await db.commit()
        await db.refresh(query_def)
        return QueryDefinitionResponse.model_validate(query_def)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create query definition: {e!s}",
        )


@router.get("/queries", response_model=list[QueryDefinitionResponse])
async def list_query_definitions(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    member: WorkspaceMemberDep,
    query_type: str | None = None,
    cluster_id: int | None = None,
) -> list[QueryDefinitionResponse]:
    """List query definitions. Filter by ?query_type and ?cluster_id."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    query = select(QueryDefinition).where(
        QueryDefinition.campaign_id == campaign_id,
    )
    if query_type is not None:
        query = query.where(QueryDefinition.query_type == query_type)
    if cluster_id is not None:
        query = query.where(QueryDefinition.intent_cluster_id == cluster_id)

    query = query.order_by(QueryDefinition.id)
    result = await db.execute(query)
    defs = result.scalars().all()
    return [QueryDefinitionResponse.model_validate(d) for d in defs]


@router.get(
    "/queries/{query_id}/versions",
    response_model=list[QueryVersionResponse],
)
async def list_query_versions(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    query_id: int,
    member: WorkspaceMemberDep,
) -> list[QueryVersionResponse]:
    """List all versions of a query definition."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    # Verify query belongs to campaign
    qd_result = await db.execute(
        select(QueryDefinition).where(
            QueryDefinition.id == query_id,
            QueryDefinition.campaign_id == campaign_id,
        )
    )
    if qd_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query definition not found in this campaign",
        )

    result = await db.execute(
        select(QueryVersion)
        .where(QueryVersion.query_definition_id == query_id)
        .order_by(QueryVersion.version.desc())
    )
    versions = result.scalars().all()
    return [QueryVersionResponse.model_validate(v) for v in versions]


@router.post(
    "/queries/{query_id}/new-version",
    response_model=QueryVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_query_version(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    query_id: int,
    current_user: CurrentUser,
    version_in: QueryVersionCreate,
    admin: WorkspaceAdminDep,
) -> QueryVersionResponse:
    """Create a new version of a query. Sets old version is_current=False."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    # Get query definition
    qd_result = await db.execute(
        select(QueryDefinition).where(
            QueryDefinition.id == query_id,
            QueryDefinition.campaign_id == campaign_id,
        )
    )
    query_def = qd_result.scalar_one_or_none()
    if query_def is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query definition not found in this campaign",
        )

    if query_def.is_retired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create new version for a retired query",
        )

    try:
        now = datetime.now(tz=UTC)

        # Mark current version as not current
        current_versions_result = await db.execute(
            select(QueryVersion).where(
                QueryVersion.query_definition_id == query_id,
                QueryVersion.is_current.is_(True),
            )
        )
        for old_version in current_versions_result.scalars().all():
            old_version.is_current = False
            old_version.effective_until = now

        # Create new version
        new_version_number = query_def.current_version + 1
        new_version = QueryVersion(
            query_definition_id=query_id,
            version=new_version_number,
            text=version_in.text,
            persona_type=version_in.persona_type,
            change_reason=version_in.change_reason,
            changed_by=current_user.id,
            is_current=True,
            effective_from=now,
        )
        db.add(new_version)

        # Update query definition current_version
        query_def.current_version = new_version_number

        await db.commit()
        await db.refresh(new_version)
        return QueryVersionResponse.model_validate(new_version)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create new query version: {e!s}",
        )


@router.post(
    "/queries/{query_id}/retire",
    response_model=QueryDefinitionResponse,
)
async def retire_query_definition(
    db: DbSession,
    workspace_id: int,
    campaign_id: int,
    query_id: int,
    admin: WorkspaceAdminDep,
) -> QueryDefinitionResponse:
    """Retire a query definition. Sets is_retired=True, is_active=False."""
    await _get_campaign_or_404(db, workspace_id, campaign_id)

    qd_result = await db.execute(
        select(QueryDefinition).where(
            QueryDefinition.id == query_id,
            QueryDefinition.campaign_id == campaign_id,
        )
    )
    query_def = qd_result.scalar_one_or_none()
    if query_def is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query definition not found in this campaign",
        )

    if query_def.is_retired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query is already retired",
        )

    try:
        query_def.is_retired = True
        query_def.is_active = False
        await db.commit()
        await db.refresh(query_def)
        return QueryDefinitionResponse.model_validate(query_def)

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retire query: {e!s}",
        )
