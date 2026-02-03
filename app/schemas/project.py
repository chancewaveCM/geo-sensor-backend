from datetime import datetime

from pydantic import BaseModel, Field

from app.core.constants import (
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    MIN_STRING_LENGTH,
)
from app.schemas.base import BaseResponseSchema


class ProjectBase(BaseModel):
    name: str
    description: str | None = None


class ProjectCreate(ProjectBase):
    name: str = Field(..., min_length=MIN_STRING_LENGTH, max_length=MAX_NAME_LENGTH)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_LENGTH)


class ProjectUpdate(BaseModel):
    name: str | None = Field(
        default=None, min_length=MIN_STRING_LENGTH, max_length=MAX_NAME_LENGTH
    )
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_LENGTH)


class ProjectResponse(ProjectBase, BaseResponseSchema):
    id: int
    owner_id: int
    created_at: datetime
