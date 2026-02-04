"""Company Profile endpoints."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.company_profile import CompanyProfile
from app.schemas.company_profile import (
    CompanyProfileCreate,
    CompanyProfileResponse,
    CompanyProfileUpdate,
)

router = APIRouter(prefix="/company-profiles", tags=["company-profiles"])


@router.post("/", response_model=CompanyProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_company_profile(
    data: CompanyProfileCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> CompanyProfile:
    """Create a new company profile."""
    profile = CompanyProfile(**data.model_dump(), owner_id=current_user.id)
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/", response_model=list[CompanyProfileResponse])
async def list_company_profiles(
    db: DbSession,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> list[CompanyProfile]:
    """List company profiles for current user."""
    result = await db.execute(
        select(CompanyProfile)
        .where(CompanyProfile.owner_id == current_user.id)
        .offset(skip)
        .limit(limit)
        .order_by(CompanyProfile.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{profile_id}", response_model=CompanyProfileResponse)
async def get_company_profile(
    profile_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> CompanyProfile:
    """Get a company profile by ID."""
    result = await db.execute(
        select(CompanyProfile).where(
            CompanyProfile.id == profile_id,
            CompanyProfile.owner_id == current_user.id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found",
        )
    return profile


@router.put("/{profile_id}", response_model=CompanyProfileResponse)
async def update_company_profile(
    profile_id: int,
    data: CompanyProfileUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> CompanyProfile:
    """Update a company profile."""
    result = await db.execute(
        select(CompanyProfile).where(
            CompanyProfile.id == profile_id,
            CompanyProfile.owner_id == current_user.id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found",
        )

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return profile


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_profile(
    profile_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Delete a company profile."""
    result = await db.execute(
        select(CompanyProfile).where(
            CompanyProfile.id == profile_id,
            CompanyProfile.owner_id == current_user.id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found",
        )

    await db.delete(profile)
    await db.commit()
