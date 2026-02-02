from pydantic import BaseModel, ConfigDict
from datetime import datetime


class BrandBase(BaseModel):
    name: str
    aliases: list[str] | None = None
    keywords: list[str] | None = None
    description: str | None = None


class BrandCreate(BrandBase):
    project_id: int


class BrandUpdate(BaseModel):
    name: str | None = None
    aliases: list[str] | None = None
    keywords: list[str] | None = None
    description: str | None = None


class BrandResponse(BrandBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    created_at: datetime
