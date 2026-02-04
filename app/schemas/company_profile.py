"""Company Profile schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CompanyProfileBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    industry: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=10)
    target_audience: str | None = None
    main_products: str | None = None
    competitors: str | None = None
    unique_value: str | None = None
    website_url: str | None = None
    project_id: int | None = None


class CompanyProfileCreate(CompanyProfileBase):
    pass


class CompanyProfileUpdate(BaseModel):
    name: str | None = None
    industry: str | None = None
    description: str | None = None
    target_audience: str | None = None
    main_products: str | None = None
    competitors: str | None = None
    unique_value: str | None = None
    website_url: str | None = None


class CompanyProfileResponse(CompanyProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime
