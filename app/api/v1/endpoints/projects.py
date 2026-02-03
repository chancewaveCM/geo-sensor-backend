"""Project management endpoints."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, Pagination
from app.core.constants import ERROR_PROJECT_NOT_FOUND
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    db: DbSession,
    current_user: CurrentUser,
    pagination: Pagination,
) -> list[ProjectResponse]:
    """List all projects for current user."""
    result = await db.execute(
        select(Project)
        .where(Project.owner_id == current_user.id)
        .offset(pagination.skip)
        .limit(pagination.limit)
    )
    projects = result.scalars().all()
    return [ProjectResponse.model_validate(p) for p in projects]


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    db: DbSession,
    current_user: CurrentUser,
    project_in: ProjectCreate,
) -> ProjectResponse:
    """Create new project."""
    project = Project(
        name=project_in.name,
        description=project_in.description,
        owner_id=current_user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    db: DbSession,
    current_user: CurrentUser,
    project_id: int,
) -> ProjectResponse:
    """Get project by ID."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == current_user.id
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=ERROR_PROJECT_NOT_FOUND)
    return ProjectResponse.model_validate(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    db: DbSession,
    current_user: CurrentUser,
    project_id: int,
    project_in: ProjectUpdate,
) -> ProjectResponse:
    """Update project."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == current_user.id
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=ERROR_PROJECT_NOT_FOUND)

    update_data = project_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    db: DbSession,
    current_user: CurrentUser,
    project_id: int,
) -> None:
    """Delete project."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == current_user.id
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=ERROR_PROJECT_NOT_FOUND)

    await db.delete(project)
    await db.commit()
