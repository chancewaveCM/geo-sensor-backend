"""Operations API for promote, change-request, parser-issue, export, archive."""

import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import (
    CurrentUser,
    DbSession,
    Pagination,
    WorkspaceAdminDep,
    WorkspaceMemberDep,
)
from app.models.enums import OperationStatus
from app.models.gallery import OperationLog
from app.schemas.gallery import (
    OperationLogCreate,
    OperationLogResponse,
    OperationReviewRequest,
)

router = APIRouter(
    prefix="/workspaces/{workspace_id}/operations",
    tags=["operations"],
)


@router.post(
    "/",
    response_model=OperationLogResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_operation(
    db: DbSession,
    workspace_id: int,
    current_user: CurrentUser,
    op_in: OperationLogCreate,
    member: WorkspaceMemberDep,
) -> OperationLogResponse:
    """Create an operation log entry. Requires membership."""
    try:
        operation = OperationLog(
            workspace_id=workspace_id,
            operation_type=op_in.operation_type,
            status=OperationStatus.PENDING.value,
            target_type=op_in.target_type,
            target_id=op_in.target_id,
            payload=json.dumps(op_in.payload) if op_in.payload else None,
            created_by=current_user.id,
        )
        db.add(operation)
        await db.commit()
        await db.refresh(operation)
        return OperationLogResponse.model_validate(operation)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create operation: {e!s}",
        )


@router.get("/", response_model=list[OperationLogResponse])
async def list_operations(
    db: DbSession,
    workspace_id: int,
    member: WorkspaceMemberDep,
    pagination: Pagination,
    operation_type: str | None = None,
    op_status: str | None = None,
) -> list[OperationLogResponse]:
    """List operation logs. Filter by type and status."""
    query = select(OperationLog).where(OperationLog.workspace_id == workspace_id)

    if operation_type is not None:
        query = query.where(OperationLog.operation_type == operation_type)
    if op_status is not None:
        query = query.where(OperationLog.status == op_status)

    query = query.order_by(OperationLog.created_at.desc())
    query = query.offset(pagination.skip).limit(pagination.limit)

    result = await db.execute(query)
    operations = result.scalars().all()
    return [OperationLogResponse.model_validate(o) for o in operations]


@router.get("/{operation_id}", response_model=OperationLogResponse)
async def get_operation(
    db: DbSession,
    workspace_id: int,
    operation_id: int,
    member: WorkspaceMemberDep,
) -> OperationLogResponse:
    """Get operation detail."""
    result = await db.execute(
        select(OperationLog).where(
            OperationLog.id == operation_id,
            OperationLog.workspace_id == workspace_id,
        )
    )
    operation = result.scalar_one_or_none()
    if operation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Operation not found",
        )
    return OperationLogResponse.model_validate(operation)


@router.post(
    "/{operation_id}/review",
    response_model=OperationLogResponse,
)
async def review_operation(
    db: DbSession,
    workspace_id: int,
    operation_id: int,
    current_user: CurrentUser,
    review_in: OperationReviewRequest,
    admin: WorkspaceAdminDep,
) -> OperationLogResponse:
    """Approve or reject an operation. Requires ADMIN role."""
    result = await db.execute(
        select(OperationLog).where(
            OperationLog.id == operation_id,
            OperationLog.workspace_id == workspace_id,
        )
    )
    operation = result.scalar_one_or_none()
    if operation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Operation not found",
        )

    if operation.status != OperationStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Operation is already {operation.status}",
        )

    try:
        operation.status = review_in.status
        operation.reviewed_by = current_user.id
        operation.reviewed_at = datetime.now(tz=UTC)
        operation.review_comment = review_in.review_comment
        await db.commit()
        await db.refresh(operation)
        return OperationLogResponse.model_validate(operation)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to review operation: {e!s}",
        )


@router.delete("/{operation_id}", status_code=status.HTTP_200_OK)
async def cancel_operation(
    db: DbSession,
    workspace_id: int,
    operation_id: int,
    current_user: CurrentUser,
    member: WorkspaceMemberDep,
) -> dict[str, str]:
    """Cancel a pending operation. Creator or ADMIN can cancel."""
    result = await db.execute(
        select(OperationLog).where(
            OperationLog.id == operation_id,
            OperationLog.workspace_id == workspace_id,
        )
    )
    operation = result.scalar_one_or_none()
    if operation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Operation not found",
        )

    if operation.status != OperationStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending operations can be cancelled",
        )

    # Only creator or admin can cancel
    if operation.created_by != current_user.id and member.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the creator or an admin can cancel this operation",
        )

    try:
        operation.status = OperationStatus.CANCELLED.value
        await db.commit()
        return {"message": "Operation cancelled"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel operation: {e!s}",
        )
