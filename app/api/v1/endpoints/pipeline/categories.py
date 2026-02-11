# app/api/v1/endpoints/pipeline/categories.py

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, get_current_user
from app.models.enums import LLMProvider
from app.models.expanded_query import ExpandedQuery
from app.models.pipeline_category import PipelineCategory
from app.models.pipeline_job import PipelineJob
from app.models.query_set import QuerySet
from app.models.user import User
from app.schemas.pipeline import (
    CategoriesListResponse,
    CategoryResponse,
    CreateCategoryRequest,
    ExpandedQueryResponse,
    QueriesListResponse,
    UpdateCategoryRequest,
)

from ._common import _add_sunset_headers

router = APIRouter()


@router.get("/jobs/{job_id}/categories", response_model=CategoriesListResponse)
async def get_categories(
    job_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
):
    """Get generated categories for a pipeline job."""
    _add_sunset_headers(response)
    # FIX #2: Get job first to access its query_set_id
    job_result = await db.execute(
        select(PipelineJob).where(
            PipelineJob.id == job_id,
            PipelineJob.owner_id == current_user.id,
        )
    )
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # FIX #2: Query categories via QuerySet, not directly via job
    # Categories belong to QuerySet (template), not PipelineJob (execution)
    result = await db.execute(
        select(PipelineCategory)
        .where(PipelineCategory.query_set_id == job.query_set_id)
        .where(PipelineCategory.llm_provider.in_([LLMProvider(p) for p in job.llm_providers]))
        .options(selectinload(PipelineCategory.expanded_queries))
        .order_by(PipelineCategory.order_index)
    )
    categories = result.scalars().all()

    return CategoriesListResponse(
        categories=[
            CategoryResponse(
                id=c.id,
                name=c.name,
                description=c.description,
                llm_provider=c.llm_provider.value,
                persona_type=c.persona_type.value,
                order_index=c.order_index,
                query_count=len(c.expanded_queries),
            )
            for c in categories
        ]
    )


@router.post("/queryset/{query_set_id}/categories", response_model=CategoryResponse)
async def create_category(
    query_set_id: int,
    request: CreateCategoryRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
):
    """Create a new category for a query set."""
    _add_sunset_headers(response)
    # Verify ownership
    qs_result = await db.execute(
        select(QuerySet).where(
            QuerySet.id == query_set_id,
            QuerySet.owner_id == current_user.id,
        )
    )
    query_set = qs_result.scalar_one_or_none()
    if not query_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QuerySet not found",
        )

    # Validate persona_type
    from app.models.enums import PersonaType
    try:
        persona_type_enum = PersonaType(request.persona_type)
    except ValueError:
        valid_types = [p.value for p in PersonaType]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid persona_type: {request.persona_type}. Valid: {valid_types}",
        )

    # Validate llm_provider
    try:
        llm_provider_enum = LLMProvider(request.llm_provider)
    except ValueError:
        valid_providers = [p.value for p in LLMProvider]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid llm_provider: {request.llm_provider}. Valid: {valid_providers}",
        )

    # Create category
    category = PipelineCategory(
        name=request.name,
        description=request.description,
        persona_type=persona_type_enum,
        llm_provider=llm_provider_enum,
        order_index=request.order_index,
        query_set_id=query_set.id,
        company_profile_id=query_set.company_profile_id,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)

    return CategoryResponse(
        id=category.id,
        name=category.name,
        description=category.description,
        llm_provider=category.llm_provider.value,
        persona_type=category.persona_type.value,
        order_index=category.order_index,
        query_count=0,
    )


@router.put("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    request: UpdateCategoryRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
):
    """Partially update a category."""
    _add_sunset_headers(response)
    # Load category with query_set for auth
    result = await db.execute(
        select(PipelineCategory)
        .where(PipelineCategory.id == category_id)
        .options(selectinload(PipelineCategory.query_set))
        .options(selectinload(PipelineCategory.expanded_queries))
    )
    category = result.scalar_one_or_none()
    if not category or category.query_set.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    # Only update fields that are not None
    if request.name is not None:
        category.name = request.name
    if request.description is not None:
        category.description = request.description

    await db.commit()
    await db.refresh(category)

    return CategoryResponse(
        id=category.id,
        name=category.name,
        description=category.description,
        llm_provider=category.llm_provider.value,
        persona_type=category.persona_type.value,
        order_index=category.order_index,
        query_count=len(category.expanded_queries),
    )


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
):
    """Delete a category (cascade deletes expanded queries)."""
    _add_sunset_headers(response)
    # Load category with query_set for auth
    result = await db.execute(
        select(PipelineCategory)
        .where(PipelineCategory.id == category_id)
        .options(selectinload(PipelineCategory.query_set))
    )
    category = result.scalar_one_or_none()
    if not category or category.query_set.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    # ORM cascade will delete expanded_queries automatically
    await db.delete(category)
    await db.commit()

    return {"message": "Category deleted"}


@router.get("/categories/{category_id}/queries", response_model=QueriesListResponse)
async def get_category_queries(
    category_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
):
    """Get expanded queries for a category."""
    _add_sunset_headers(response)
    # Load category with query_set for auth
    result = await db.execute(
        select(PipelineCategory)
        .where(PipelineCategory.id == category_id)
        .options(selectinload(PipelineCategory.query_set))
    )
    category = result.scalar_one_or_none()
    if not category or category.query_set.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    # Load expanded queries with raw_responses for response_count
    queries_result = await db.execute(
        select(ExpandedQuery)
        .where(ExpandedQuery.category_id == category_id)
        .options(selectinload(ExpandedQuery.raw_responses))
        .order_by(ExpandedQuery.order_index)
    )
    queries = queries_result.scalars().all()

    return QueriesListResponse(
        queries=[
            ExpandedQueryResponse(
                id=q.id,
                text=q.text,
                order_index=q.order_index,
                status=q.status,
                category_id=q.category_id,
                response_count=len(q.raw_responses),
            )
            for q in queries
        ],
        total=len(queries),
    )
