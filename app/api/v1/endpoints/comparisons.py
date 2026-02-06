"""Comparison snapshot endpoints for comparing LLM responses across runs/dates/versions."""

import json

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import (
    CurrentUser,
    DbSession,
    Pagination,
    WorkspaceMemberDep,
)
from app.models.gallery import ComparisonSnapshot
from app.schemas.gallery import (
    ComparisonSnapshotCreate,
    ComparisonSnapshotResponse,
)

router = APIRouter(
    prefix="/workspaces/{workspace_id}/comparisons",
    tags=["comparisons"],
)


@router.post(
    "/",
    response_model=ComparisonSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comparison(
    db: DbSession,
    workspace_id: int,
    current_user: CurrentUser,
    comparison_in: ComparisonSnapshotCreate,
    member: WorkspaceMemberDep,
) -> ComparisonSnapshotResponse:
    """Create a comparison snapshot. Requires membership."""
    try:
        snapshot = ComparisonSnapshot(
            workspace_id=workspace_id,
            name=comparison_in.name,
            comparison_type=comparison_in.comparison_type,
            config=json.dumps(comparison_in.config),
            notes=comparison_in.notes,
            created_by=current_user.id,
        )
        db.add(snapshot)
        await db.commit()
        await db.refresh(snapshot)
        return ComparisonSnapshotResponse.model_validate(snapshot)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create comparison: {e!s}",
        )


@router.get("/", response_model=list[ComparisonSnapshotResponse])
async def list_comparisons(
    db: DbSession,
    workspace_id: int,
    member: WorkspaceMemberDep,
    pagination: Pagination,
    comparison_type: str | None = None,
) -> list[ComparisonSnapshotResponse]:
    """List comparison snapshots. Filter by ?comparison_type."""
    query = select(ComparisonSnapshot).where(
        ComparisonSnapshot.workspace_id == workspace_id,
    )
    if comparison_type is not None:
        query = query.where(ComparisonSnapshot.comparison_type == comparison_type)

    query = query.order_by(ComparisonSnapshot.created_at.desc())
    query = query.offset(pagination.skip).limit(pagination.limit)

    result = await db.execute(query)
    snapshots = result.scalars().all()
    return [ComparisonSnapshotResponse.model_validate(s) for s in snapshots]


@router.get("/{comparison_id}", response_model=ComparisonSnapshotResponse)
async def get_comparison(
    db: DbSession,
    workspace_id: int,
    comparison_id: int,
    member: WorkspaceMemberDep,
) -> ComparisonSnapshotResponse:
    """Get a comparison snapshot detail."""
    result = await db.execute(
        select(ComparisonSnapshot).where(
            ComparisonSnapshot.id == comparison_id,
            ComparisonSnapshot.workspace_id == workspace_id,
        )
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comparison snapshot not found",
        )
    return ComparisonSnapshotResponse.model_validate(snapshot)


@router.delete("/{comparison_id}", status_code=status.HTTP_200_OK)
async def delete_comparison(
    db: DbSession,
    workspace_id: int,
    comparison_id: int,
    current_user: CurrentUser,
    member: WorkspaceMemberDep,
) -> dict[str, str]:
    """Delete a comparison snapshot. Creator or ADMIN can delete."""
    result = await db.execute(
        select(ComparisonSnapshot).where(
            ComparisonSnapshot.id == comparison_id,
            ComparisonSnapshot.workspace_id == workspace_id,
        )
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comparison snapshot not found",
        )

    # Only creator or admin can delete
    if snapshot.created_by != current_user.id and member.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the creator or an admin can delete this comparison",
        )

    try:
        await db.delete(snapshot)
        await db.commit()
        return {"message": "Comparison deleted"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete comparison: {e!s}",
        )
