# app/api/v1/endpoints/pipeline/query_sets.py

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, get_current_user
from app.models.company_profile import CompanyProfile
from app.models.enums import PipelineStatus
from app.models.expanded_query import ExpandedQuery
from app.models.pipeline_category import PipelineCategory
from app.models.pipeline_job import PipelineJob
from app.models.query_set import QuerySet
from app.models.raw_llm_response import RawLLMResponse
from app.models.user import User
from app.schemas.pipeline import (
    QuerySetDetailCategoryItem,
    QuerySetDetailJobItem,
    QuerySetDetailResponse,
    QuerySetHistoryItem,
    QuerySetHistoryResponse,
    QuerySetListResponse,
    QuerySetResponse,
    RerunQuerySetRequest,
    StartPipelineResponse,
)
from app.services.pipeline.background_manager import BackgroundJobManager

from ._common import _add_sunset_headers, _build_pipeline_services, _validate_llm_providers

router = APIRouter()


@router.get("/queryset", response_model=QuerySetListResponse)
async def list_query_sets(
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
    company_profile_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
):
    """List all QuerySets owned by user."""
    _add_sunset_headers(response)
    # Subquery for last job status
    last_job_status_subq = (
        select(PipelineJob.status)
        .where(PipelineJob.query_set_id == QuerySet.id)
        .order_by(PipelineJob.created_at.desc())
        .limit(1)
        .correlate(QuerySet)
        .scalar_subquery()
    )

    # Subquery for last run at
    last_run_at_subq = (
        select(PipelineJob.started_at)
        .where(PipelineJob.query_set_id == QuerySet.id)
        .order_by(PipelineJob.created_at.desc())
        .limit(1)
        .correlate(QuerySet)
        .scalar_subquery()
    )

    # Subquery for total responses
    total_responses_subq = (
        select(func.count(RawLLMResponse.id))
        .join(ExpandedQuery, RawLLMResponse.query_id == ExpandedQuery.id)
        .join(PipelineCategory, ExpandedQuery.category_id == PipelineCategory.id)
        .where(PipelineCategory.query_set_id == QuerySet.id)
        .correlate(QuerySet)
        .scalar_subquery()
    )

    # Subquery for job count
    job_count_subq = (
        select(func.count(PipelineJob.id))
        .where(PipelineJob.query_set_id == QuerySet.id)
        .correlate(QuerySet)
        .scalar_subquery()
    )

    query = (
        select(
            QuerySet,
            last_job_status_subq.label("last_job_status"),
            last_run_at_subq.label("last_run_at"),
            total_responses_subq.label("total_responses"),
            job_count_subq.label("job_count"),
        )
        .where(QuerySet.owner_id == current_user.id)
    )

    if company_profile_id:
        query = query.where(QuerySet.company_profile_id == company_profile_id)

    query = query.order_by(QuerySet.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    # Get total count
    count_query = select(func.count(QuerySet.id)).where(QuerySet.owner_id == current_user.id)
    if company_profile_id:
        count_query = count_query.where(QuerySet.company_profile_id == company_profile_id)
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    return QuerySetListResponse(
        query_sets=[
            QuerySetResponse(
                id=row.QuerySet.id,
                name=row.QuerySet.name,
                description=row.QuerySet.description,
                category_count=row.QuerySet.category_count,
                queries_per_category=row.QuerySet.queries_per_category,
                company_profile_id=row.QuerySet.company_profile_id,
                created_at=row.QuerySet.created_at,
                job_count=row.job_count or 0,
                last_job_status=row.last_job_status if row.last_job_status else None,
                last_run_at=row.last_run_at,
                total_responses=row.total_responses or 0,
            )
            for row in rows
        ],
        total=total,
    )


@router.get("/queryset/{query_set_id}/detail", response_model=QuerySetDetailResponse)
async def get_query_set_detail(
    query_set_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
):
    """Get detailed information about a QuerySet including categories and job history."""
    _add_sunset_headers(response)
    # Verify ownership and load with relationships
    result = await db.execute(
        select(QuerySet)
        .where(
            QuerySet.id == query_set_id,
            QuerySet.owner_id == current_user.id,
        )
        .options(
            selectinload(QuerySet.categories).selectinload(PipelineCategory.expanded_queries),
            selectinload(QuerySet.pipeline_jobs),
        )
    )
    query_set = result.scalar_one_or_none()
    if not query_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QuerySet not found",
        )

    # Build category items with query counts
    categories = [
        QuerySetDetailCategoryItem(
            id=cat.id,
            name=cat.name,
            description=cat.description,
            llm_provider=cat.llm_provider.value,
            persona_type=cat.persona_type.value,
            order_index=cat.order_index,
            query_count=len(cat.expanded_queries),
        )
        for cat in sorted(query_set.categories, key=lambda c: c.order_index)
    ]

    # Get last job (most recent)
    last_job = None
    if query_set.pipeline_jobs:
        latest_job = sorted(query_set.pipeline_jobs, key=lambda j: j.created_at, reverse=True)[0]
        last_job = QuerySetDetailJobItem(
            id=latest_job.id,
            status=latest_job.status,
            llm_providers=latest_job.llm_providers,
            total_queries=latest_job.total_queries,
            completed_queries=latest_job.completed_queries,
            failed_queries=latest_job.failed_queries,
            started_at=latest_job.started_at,
            completed_at=latest_job.completed_at,
        )

    # Count total responses across all categories
    response_count_result = await db.execute(
        select(func.count(RawLLMResponse.id))
        .join(ExpandedQuery, RawLLMResponse.query_id == ExpandedQuery.id)
        .join(PipelineCategory, ExpandedQuery.category_id == PipelineCategory.id)
        .where(PipelineCategory.query_set_id == query_set_id)
    )
    total_responses = response_count_result.scalar() or 0

    return QuerySetDetailResponse(
        id=query_set.id,
        name=query_set.name,
        description=query_set.description,
        category_count=query_set.category_count,
        queries_per_category=query_set.queries_per_category,
        company_profile_id=query_set.company_profile_id,
        created_at=query_set.created_at,
        categories=categories,
        last_job=last_job,
        total_jobs=len(query_set.pipeline_jobs),
        total_responses=total_responses,
    )


@router.get("/queryset/{query_set_id}/history", response_model=QuerySetHistoryResponse)
async def get_query_set_history(
    query_set_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
):
    """Get execution history for a QuerySet (for time-series analysis)."""
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

    # Get all PipelineJobs for this QuerySet
    jobs_result = await db.execute(
        select(PipelineJob)
        .where(PipelineJob.query_set_id == query_set_id)
        .order_by(PipelineJob.created_at.desc())
    )
    jobs = jobs_result.scalars().all()

    return QuerySetHistoryResponse(
        query_set_id=query_set.id,
        query_set_name=query_set.name,
        executions=[
            QuerySetHistoryItem(
                job_id=j.id,
                status=j.status,
                completed_queries=j.completed_queries,
                failed_queries=j.failed_queries,
                started_at=j.started_at,
                completed_at=j.completed_at,
            )
            for j in jobs
        ],
        total_executions=len(jobs),
    )


@router.post("/queryset/{query_set_id}/rerun", response_model=StartPipelineResponse)
async def rerun_query_set(
    query_set_id: int,
    request: RerunQuerySetRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
):
    """Re-run an existing QuerySet to create new time-series data point."""
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

    # Get company profile
    profile_result = await db.execute(
        select(CompanyProfile).where(
            CompanyProfile.id == query_set.company_profile_id,
        )
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found",
        )

    # Validate providers
    _validate_llm_providers(request.llm_providers)

    # Create new PipelineJob referencing existing QuerySet (rerun)
    job = PipelineJob(
        query_set_id=query_set.id,
        company_profile_id=query_set.company_profile_id,
        owner_id=current_user.id,
        llm_providers=request.llm_providers,
        status=PipelineStatus.PENDING,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Build services
    orchestrator, bg_db = _build_pipeline_services(request.llm_providers)

    # Start background execution with is_rerun=True (skips category/query generation)
    try:
        await BackgroundJobManager.start_job(
            job.id,
            orchestrator.start_pipeline(
                job_id=job.id,
                company_profile_id=profile.id,
                query_set_id=query_set.id,
                is_rerun=True,
            ),
        )
    except Exception:
        await bg_db.close()
        raise

    estimated = (
        query_set.category_count
        * query_set.queries_per_category
        * len(request.llm_providers)
    )

    return StartPipelineResponse(
        job_id=job.id,
        status=job.status,
        message="Re-run pipeline job created and started",
        estimated_queries=estimated,
    )
