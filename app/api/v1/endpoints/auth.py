"""Authentication endpoints."""

import base64
import json
import re
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.enums import WorkspaceRole
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.token import Token
from app.schemas.user import (
    AvatarUploadRequest,
    PasswordChangeRequest,
    UserCreate,
    UserProfileUpdate,
    UserResponse,
)
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

PROFILE_MUTABLE_FIELDS = {"full_name", "avatar_url", "notification_preferences"}


def _generate_workspace_slug(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name.lower().strip())
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "workspace"


async def _ensure_unique_workspace_slug(db: DbSession, base_slug: str) -> str:
    slug = base_slug
    counter = 2
    while True:
        result = await db.execute(select(Workspace.id).where(Workspace.slug == slug))
        if result.scalar_one_or_none() is None:
            return slug
        slug = f"{base_slug}-{counter}"
        counter += 1


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
async def login(
    request: Request,
    db: DbSession,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """Login and get access token."""
    user = await user_service.authenticate_user(db, form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )

    # Auto-create workspace for users who don't have one (legacy accounts)
    membership_check = await db.execute(
        select(WorkspaceMember.id).where(WorkspaceMember.user_id == user.id).limit(1)
    )
    if membership_check.scalar_one_or_none() is None:
        ws_name = f"{user.full_name or user.email.split('@')[0]}'s Workspace"
        base_slug = _generate_workspace_slug(ws_name)
        unique_slug = await _ensure_unique_workspace_slug(db, base_slug)
        workspace = Workspace(name=ws_name, slug=unique_slug)
        db.add(workspace)
        await db.flush()
        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceRole.ADMIN.value,
        )
        db.add(member)
        await db.commit()

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )

    return Token(access_token=access_token, token_type="bearer")


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def register(
    request: Request,
    db: DbSession,
    user_in: UserCreate,
) -> UserResponse:
    """Register new user."""
    existing_user = await user_service.get_user_by_email(db, user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    try:
        user = await user_service.create_user(db, user_in, auto_commit=False)
        await db.flush()  # Ensure user.id is available before creating membership

        # Auto-create default workspace for new user
        ws_name = f"{user.full_name or user.email.split('@')[0]}'s Workspace"
        base_slug = _generate_workspace_slug(ws_name)
        unique_slug = await _ensure_unique_workspace_slug(db, base_slug)

        workspace = Workspace(name=ws_name, slug=unique_slug)
        db.add(workspace)
        await db.flush()  # Get workspace.id

        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceRole.ADMIN.value,
        )
        db.add(member)
        await db.commit()
        await db.refresh(user)
        return UserResponse.model_validate(user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Registration conflict detected. Please retry.",
        )
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete registration",
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: CurrentUser,
) -> UserResponse:
    """Get current user info."""
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
@limiter.limit("10/minute")
async def update_profile(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    profile_in: UserProfileUpdate,
) -> UserResponse:
    """Update current user profile."""
    update_data = profile_in.model_dump(exclude_unset=True)

    # If notification_preferences is a dict, convert to JSON string
    if "notification_preferences" in update_data:
        notif_prefs = update_data["notification_preferences"]
        if isinstance(notif_prefs, dict):
            update_data["notification_preferences"] = json.dumps(notif_prefs)

    # Filter to only mutable fields
    update_data = {k: v for k, v in update_data.items() if k in PROFILE_MUTABLE_FIELDS}

    for field, value in update_data.items():
        setattr(current_user, field, value)

    await db.commit()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.post("/change-password", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    password_in: PasswordChangeRequest,
) -> dict:
    """Change current user password."""
    if not verify_password(password_in.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if verify_password(password_in.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    current_user.hashed_password = get_password_hash(password_in.new_password)
    await db.commit()
    return {"message": "Password changed successfully"}


@router.post("/me/avatar", response_model=UserResponse)
@limiter.limit("5/minute")
async def upload_avatar(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    avatar_in: AvatarUploadRequest,
) -> UserResponse:
    """Upload avatar as Base64 (MVP: stored directly in DB)."""
    # Check base64 string length before decoding (base64 is ~33% larger than binary)
    max_base64_len = int(2 * 1024 * 1024 * 1.34)  # ~2.68MB for 2MB binary
    if len(avatar_in.avatar_data) > max_base64_len:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Avatar image must be less than 2MB",
        )

    # Validate base64 and magic bytes
    try:
        decoded = base64.b64decode(avatar_in.avatar_data, validate=True)
        if len(decoded) > 2 * 1024 * 1024:  # 2MB limit
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Avatar image must be less than 2MB",
            )

        # Validate magic bytes
        allowed_magic = {
            b'\x89PNG': 'image/png',
            b'\xff\xd8\xff': 'image/jpeg',
            b'GIF87': 'image/gif',
            b'GIF89': 'image/gif',
            b'RIFF': 'image/webp',
        }
        if not any(decoded.startswith(magic) for magic in allowed_magic):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="지원하지 않는 이미지 형식입니다",
            )
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 image data",
        ) from exc

    # Store as data URI
    current_user.avatar_url = f"data:{avatar_in.content_type};base64,{avatar_in.avatar_data}"
    await db.commit()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.delete("/me", status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def delete_account(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Soft delete current user account (set is_active=False)."""
    current_user.is_active = False
    await db.commit()
    return {"message": "Account deactivated successfully"}
