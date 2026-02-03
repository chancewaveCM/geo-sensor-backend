from datetime import datetime

from pydantic import BaseModel, Field

from app.core.constants import (
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    MIN_STRING_LENGTH,
)
from app.schemas.base import BaseResponseSchema


class BrandBase(BaseModel):
    name: str
    aliases: list[str] | None = None
    keywords: list[str] | None = None
    description: str | None = None


class BrandCreate(BrandBase):
    name: str = Field(..., min_length=MIN_STRING_LENGTH, max_length=MAX_NAME_LENGTH)
    project_id: int = Field(..., gt=0)


class BrandUpdate(BaseModel):
    name: str | None = Field(
        default=None, min_length=MIN_STRING_LENGTH, max_length=MAX_NAME_LENGTH
    )
    aliases: list[str] | None = None
    keywords: list[str] | None = None
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_LENGTH)


class BrandResponse(BrandBase, BaseResponseSchema):
    id: int
    project_id: int
    created_at: datetime
