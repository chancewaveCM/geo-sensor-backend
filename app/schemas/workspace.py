"""Pydantic schemas for Workspace operations."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# --- Workspace ---

class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    member_count: int | None = None
    my_role: str | None = None


class WorkspaceListResponse(BaseModel):
    items: list[WorkspaceResponse]
    total: int


# --- WorkspaceMember ---

class WorkspaceMemberCreate(BaseModel):
    """Invite a user to workspace by email."""
    email: EmailStr = Field(..., description="Email of user to invite")
    role: str = Field(default="user", pattern="^(admin|user)$")


class WorkspaceMemberUpdate(BaseModel):
    role: str = Field(..., pattern="^(admin|user)$")


class WorkspaceMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    email: str | None = None
    full_name: str | None = None
    role: str
    joined_at: datetime | None = None
    created_at: datetime
