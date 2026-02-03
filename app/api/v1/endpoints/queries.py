"""Query management endpoints."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, Pagination, verify_project_access
from app.core.constants import ERROR_QUERY_NOT_FOUND
from app.models.project import Project
from app.models.query import Query, QueryStatus
from app.schemas.query import QueryCreate, QueryResponse

router = APIRouter(prefix="/queries", tags=["queries"])


@router.get("/", response_model=list[QueryResponse])
async def list_queries(
    db: DbSession,
    current_user: CurrentUser,
    project_id: int,
    pagination: Pagination,
) -> list[QueryResponse]:
    """List all queries for a project."""
    await verify_project_access(db, project_id, current_user.id)

    result = await db.execute(
        select(Query)
        .where(Query.project_id == project_id)
        .offset(pagination.skip)
        .limit(pagination.limit)
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
    await verify_project_access(db, query_in.project_id, current_user.id)

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
        raise HTTPException(status_code=404, detail=ERROR_QUERY_NOT_FOUND)
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
        raise HTTPException(status_code=404, detail=ERROR_QUERY_NOT_FOUND)

    await db.delete(query)
    await db.commit()
