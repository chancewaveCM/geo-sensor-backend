"""API dependencies for authentication and database access."""

from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import (
    DEFAULT_LIMIT,
    DEFAULT_SKIP,
    ERROR_FORBIDDEN_INACTIVE,
    ERROR_FORBIDDEN_PRIVILEGES,
    ERROR_PROJECT_NOT_FOUND,
    ERROR_UNAUTHORIZED,
    MAX_LIMIT,
)
from app.core.security import verify_token
from app.db.session import get_db
from app.models.project import Project
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    """Get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ERROR_UNAUTHORIZED,
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = verify_token(token)
    if payload is None:
        raise credentials_exception

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_FORBIDDEN_INACTIVE,
        )
    return current_user


async def get_current_superuser(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Get current superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_FORBIDDEN_PRIVILEGES,
        )
    return current_user


# Type aliases for cleaner route signatures
CurrentUser = Annotated[User, Depends(get_current_active_user)]
CurrentSuperuser = Annotated[User, Depends(get_current_superuser)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


# Pagination dependency
class PaginationParams(BaseModel):
    """Pagination parameters."""

    skip: int
    limit: int


def get_pagination_params(
    skip: int = Query(default=DEFAULT_SKIP, ge=0),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
) -> PaginationParams:
    """Get pagination parameters from query string."""
    return PaginationParams(skip=skip, limit=limit)


Pagination = Annotated[PaginationParams, Depends(get_pagination_params)]


# Project access verification
async def verify_project_access(
    db: AsyncSession,
    project_id: int,
    user_id: int,
) -> Project:
    """Verify user has access to project and return it."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=ERROR_PROJECT_NOT_FOUND)
    return project
