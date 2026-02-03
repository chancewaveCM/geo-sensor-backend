"""Brand management endpoints."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, Pagination, verify_project_access
from app.core.constants import ERROR_BRAND_NOT_FOUND
from app.models.brand import Brand
from app.models.project import Project
from app.schemas.brand import BrandCreate, BrandResponse, BrandUpdate

router = APIRouter(prefix="/brands", tags=["brands"])


@router.get("/", response_model=list[BrandResponse])
async def list_brands(
    db: DbSession,
    current_user: CurrentUser,
    project_id: int,
    pagination: Pagination,
) -> list[BrandResponse]:
    """List all brands for a project."""
    await verify_project_access(db, project_id, current_user.id)

    result = await db.execute(
        select(Brand)
        .where(Brand.project_id == project_id)
        .offset(pagination.skip)
        .limit(pagination.limit)
    )
    brands = result.scalars().all()
    return [BrandResponse.model_validate(b) for b in brands]


@router.post("/", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
async def create_brand(
    db: DbSession,
    current_user: CurrentUser,
    brand_in: BrandCreate,
) -> BrandResponse:
    """Create new brand."""
    await verify_project_access(db, brand_in.project_id, current_user.id)

    brand = Brand(
        name=brand_in.name,
        aliases=brand_in.aliases,
        keywords=brand_in.keywords,
        description=brand_in.description,
        project_id=brand_in.project_id,
    )
    db.add(brand)
    await db.commit()
    await db.refresh(brand)
    return BrandResponse.model_validate(brand)


@router.get("/{brand_id}", response_model=BrandResponse)
async def get_brand(
    db: DbSession,
    current_user: CurrentUser,
    brand_id: int,
) -> BrandResponse:
    """Get brand by ID."""
    result = await db.execute(
        select(Brand)
        .join(Project)
        .where(Brand.id == brand_id, Project.owner_id == current_user.id)
    )
    brand = result.scalar_one_or_none()
    if brand is None:
        raise HTTPException(status_code=404, detail=ERROR_BRAND_NOT_FOUND)
    return BrandResponse.model_validate(brand)


@router.put("/{brand_id}", response_model=BrandResponse)
async def update_brand(
    db: DbSession,
    current_user: CurrentUser,
    brand_id: int,
    brand_in: BrandUpdate,
) -> BrandResponse:
    """Update brand."""
    result = await db.execute(
        select(Brand)
        .join(Project)
        .where(Brand.id == brand_id, Project.owner_id == current_user.id)
    )
    brand = result.scalar_one_or_none()
    if brand is None:
        raise HTTPException(status_code=404, detail=ERROR_BRAND_NOT_FOUND)

    update_data = brand_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(brand, field, value)

    await db.commit()
    await db.refresh(brand)
    return BrandResponse.model_validate(brand)


@router.delete("/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_brand(
    db: DbSession,
    current_user: CurrentUser,
    brand_id: int,
) -> None:
    """Delete brand."""
    result = await db.execute(
        select(Brand)
        .join(Project)
        .where(Brand.id == brand_id, Project.owner_id == current_user.id)
    )
    brand = result.scalar_one_or_none()
    if brand is None:
        raise HTTPException(status_code=404, detail=ERROR_BRAND_NOT_FOUND)

    await db.delete(brand)
    await db.commit()
