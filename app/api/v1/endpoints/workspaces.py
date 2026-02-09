"""Workspace management endpoints."""

import logging
import re

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, WorkspaceAdminDep, WorkspaceMemberDep
from app.models.enums import WorkspaceRole
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberCreate,
    WorkspaceMemberResponse,
    WorkspaceMemberUpdate,
    WorkspaceResponse,
    WorkspaceUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def generate_slug(name: str) -> str:
    """Generate URL-safe slug from name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


async def ensure_unique_slug(db: DbSession, base_slug: str) -> str:
    """Ensure slug is unique by appending number if needed."""
    slug = base_slug
    counter = 2
    while True:
        result = await db.execute(select(Workspace).where(Workspace.slug == slug))
        if result.scalar_one_or_none() is None:
            return slug
        slug = f"{base_slug}-{counter}"
        counter += 1


@router.post("/", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    db: DbSession,
    current_user: CurrentUser,
    workspace_in: WorkspaceCreate,
) -> WorkspaceResponse:
    """Create new workspace and add creator as ADMIN."""
    try:
        # Generate unique slug
        base_slug = generate_slug(workspace_in.name)
        unique_slug = await ensure_unique_slug(db, base_slug)

        # Create workspace
        workspace = Workspace(
            name=workspace_in.name,
            slug=unique_slug,
            description=workspace_in.description,
        )
        db.add(workspace)
        await db.flush()  # Get workspace.id before creating member

        # Create workspace member with ADMIN role for creator
        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=current_user.id,
            role=WorkspaceRole.ADMIN.value,
            invited_by=None,  # Creator is not invited
        )
        db.add(member)

        await db.commit()
        await db.refresh(workspace)

        # Build response
        response = WorkspaceResponse.model_validate(workspace)
        response.member_count = 1
        response.my_role = WorkspaceRole.ADMIN.value
        return response

    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create workspace",
        )


@router.get("/", response_model=list[WorkspaceResponse])
async def list_my_workspaces(
    db: DbSession,
    current_user: CurrentUser,
) -> list[WorkspaceResponse]:
    """List all workspaces where current user is a member."""
    result = await db.execute(
        select(WorkspaceMember)
        .options(selectinload(WorkspaceMember.workspace))
        .where(WorkspaceMember.user_id == current_user.id)
    )
    members = result.scalars().all()

    responses = []
    for member in members:
        workspace = member.workspace

        # Count members
        count_result = await db.execute(
            select(func.count(WorkspaceMember.id)).where(
                WorkspaceMember.workspace_id == workspace.id
            )
        )
        member_count = count_result.scalar() or 0

        response = WorkspaceResponse.model_validate(workspace)
        response.member_count = member_count
        response.my_role = member.role
        responses.append(response)

    return responses


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    db: DbSession,
    workspace_id: int,
    member: WorkspaceMemberDep,
) -> WorkspaceResponse:
    """Get workspace detail. Requires membership."""
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    # Count members
    count_result = await db.execute(
        select(func.count(WorkspaceMember.id)).where(
            WorkspaceMember.workspace_id == workspace_id
        )
    )
    member_count = count_result.scalar() or 0

    response = WorkspaceResponse.model_validate(workspace)
    response.member_count = member_count
    response.my_role = member.role
    return response


@router.put("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    db: DbSession,
    workspace_id: int,
    workspace_in: WorkspaceUpdate,
    admin: WorkspaceAdminDep,
) -> WorkspaceResponse:
    """Update workspace. Requires ADMIN role."""
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    try:
        update_data = workspace_in.model_dump(exclude_unset=True)

        # Regenerate slug if name changed
        if "name" in update_data:
            base_slug = generate_slug(update_data["name"])
            # Only check uniqueness if slug actually changed
            if base_slug != workspace.slug:
                unique_slug = await ensure_unique_slug(db, base_slug)
                workspace.slug = unique_slug

        for field, value in update_data.items():
            setattr(workspace, field, value)

        await db.commit()
        await db.refresh(workspace)

        # Count members
        count_result = await db.execute(
            select(func.count(WorkspaceMember.id)).where(
                WorkspaceMember.workspace_id == workspace_id
            )
        )
        member_count = count_result.scalar() or 0

        response = WorkspaceResponse.model_validate(workspace)
        response.member_count = member_count
        response.my_role = admin.role
        return response

    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update workspace",
        )


@router.delete("/{workspace_id}", status_code=status.HTTP_200_OK)
async def delete_workspace(
    db: DbSession,
    workspace_id: int,
    admin: WorkspaceAdminDep,
) -> dict[str, str]:
    """Delete workspace. Requires ADMIN role."""
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    try:
        await db.delete(workspace)
        await db.commit()
        return {"message": "Workspace deleted"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete workspace",
        )


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberResponse])
async def list_workspace_members(
    db: DbSession,
    workspace_id: int,
    member: WorkspaceMemberDep,
) -> list[WorkspaceMemberResponse]:
    """List all members of workspace. Requires membership."""
    result = await db.execute(
        select(WorkspaceMember)
        .options(selectinload(WorkspaceMember.user))
        .where(WorkspaceMember.workspace_id == workspace_id)
    )
    members = result.scalars().all()

    responses = []
    for m in members:
        response = WorkspaceMemberResponse.model_validate(m)
        response.email = m.user.email
        response.full_name = m.user.full_name
        responses.append(response)

    return responses


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_workspace_member(
    db: DbSession,
    current_user: CurrentUser,
    workspace_id: int,
    member_in: WorkspaceMemberCreate,
    admin: WorkspaceAdminDep,
) -> WorkspaceMemberResponse:
    """Invite user to workspace by email. Requires ADMIN role."""
    # Find user by email
    result = await db.execute(select(User).where(User.email == member_in.email))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email {member_in.email} not found",
        )

    # Check if already a member
    existing_result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if existing_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this workspace",
        )

    try:
        # Create workspace member
        new_member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user.id,
            role=member_in.role,
            invited_by=current_user.id,
        )
        db.add(new_member)
        await db.commit()
        await db.refresh(new_member)

        # Load user relationship
        await db.execute(
            select(WorkspaceMember)
            .options(selectinload(WorkspaceMember.user))
            .where(WorkspaceMember.id == new_member.id)
        )
        await db.refresh(new_member)

        response = WorkspaceMemberResponse.model_validate(new_member)
        response.email = user.email
        response.full_name = user.full_name
        return response

    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to invite member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invite member",
        )


@router.patch(
    "/{workspace_id}/members/{user_id}",
    response_model=WorkspaceMemberResponse,
)
async def change_member_role(
    db: DbSession,
    workspace_id: int,
    user_id: int,
    member_update: WorkspaceMemberUpdate,
    admin: WorkspaceAdminDep,
) -> WorkspaceMemberResponse:
    """Change member's role. Requires ADMIN role. Cannot demote last ADMIN."""
    # Get target member
    result = await db.execute(
        select(WorkspaceMember)
        .options(selectinload(WorkspaceMember.user))
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    target_member = result.scalar_one_or_none()

    if target_member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in this workspace",
        )

    # If demoting from ADMIN, check if they're the last admin
    is_admin = target_member.role == WorkspaceRole.ADMIN.value
    is_demotion = member_update.role != WorkspaceRole.ADMIN.value
    if is_admin and is_demotion:
        admin_count_result = await db.execute(
            select(func.count(WorkspaceMember.id)).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == WorkspaceRole.ADMIN.value,
            )
        )
        admin_count = admin_count_result.scalar() or 0

        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last admin of the workspace",
            )

    try:
        target_member.role = member_update.role
        await db.commit()
        await db.refresh(target_member)

        response = WorkspaceMemberResponse.model_validate(target_member)
        response.email = target_member.user.email
        response.full_name = target_member.user.full_name
        return response

    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update member role: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update member role",
        )


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_200_OK)
async def remove_workspace_member(
    db: DbSession,
    workspace_id: int,
    user_id: int,
    admin: WorkspaceAdminDep,
) -> dict[str, str]:
    """Remove member from workspace. Requires ADMIN role. Cannot remove last ADMIN."""
    # Get target member
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    target_member = result.scalar_one_or_none()

    if target_member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in this workspace",
        )

    # If removing an ADMIN, check if they're the last admin
    if target_member.role == WorkspaceRole.ADMIN.value:
        admin_count_result = await db.execute(
            select(func.count(WorkspaceMember.id)).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == WorkspaceRole.ADMIN.value,
            )
        )
        admin_count = admin_count_result.scalar() or 0

        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last admin of the workspace",
            )

    try:
        await db.delete(target_member)
        await db.commit()
        return {"message": "Member removed"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to remove member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove member",
        )


@router.get("/{workspace_id}/shared-profiles")
async def list_shared_company_profiles(
    db: DbSession,
    workspace_id: int,
    member: WorkspaceMemberDep,
) -> list[dict]:
    """List company profiles shared within workspace via campaigns."""
    from app.models.campaign import Campaign, CampaignCompany
    from app.models.company_profile import CompanyProfile

    result = await db.execute(
        select(CompanyProfile)
        .distinct()
        .join(CampaignCompany, CompanyProfile.id == CampaignCompany.company_profile_id)
        .join(Campaign, CampaignCompany.campaign_id == Campaign.id)
        .where(Campaign.workspace_id == workspace_id)
    )
    profiles = result.scalars().all()

    return [
        {
            "id": p.id,
            "name": p.name,
            "domain": p.domain if hasattr(p, "domain") else None,
        }
        for p in profiles
    ]
