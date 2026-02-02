"""Query management endpoints."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import DbSession, CurrentUser
from app.models.query import Query, QueryStatus
from app.models.project import Project
from app.schemas.query import QueryCreate, QueryResponse

router = APIRouter(prefix="/queries", tags=["queries"])


@router.get("/", response_model=list[QueryResponse])
async def list_queries(
    db: DbSession,
    current_user: CurrentUser,
    project_id: int,
    skip: int = 0,
    limit: int = 100,
) -> list[QueryResponse]:
    """List all queries for a project."""
    # Verify project access
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Query)
        .where(Query.project_id == project_id)
        .offset(skip)
        .limit(limit)
    )
    queries = result.scalars().all()
    return [QueryResponse.model_validate(q) for q in queries]


@router.post("/", response_model=QueryResponse, status_code=status.HTTP_201_CREATED)
async def create_query(
    db: DbSession,
    current_user: CurrentUser,
    query_in: QueryCreate,
) -> QueryResponse:
    """Create new query."""
    # Verify project access
    result = await db.execute(
        select(Project).where(
            Project.id == query_in.project_id,
            Project.owner_id == current_user.id
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Project not found")

    query = Query(
        text=query_in.text,
        project_id=query_in.project_id,
        status=QueryStatus.PENDING,
    )
    db.add(query)
    await db.commit()
    await db.refresh(query)
    return QueryResponse.model_validate(query)


@router.get("/{query_id}", response_model=QueryResponse)
async def get_query(
    db: DbSession,
    current_user: CurrentUser,
    query_id: int,
) -> QueryResponse:
    """Get query by ID."""
    result = await db.execute(
        select(Query)
        .join(Project)
        .where(Query.id == query_id, Project.owner_id == current_user.id)
    )
    query = result.scalar_one_or_none()
    if query is None:
        raise HTTPException(status_code=404, detail="Query not found")
    return QueryResponse.model_validate(query)


@router.delete("/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_query(
    db: DbSession,
    current_user: CurrentUser,
    query_id: int,
) -> None:
    """Delete query."""
    result = await db.execute(
        select(Query)
        .join(Project)
        .where(Query.id == query_id, Project.owner_id == current_user.id)
    )
    query = result.scalar_one_or_none()
    if query is None:
        raise HTTPException(status_code=404, detail="Query not found")

    await db.delete(query)
    await db.commit()
