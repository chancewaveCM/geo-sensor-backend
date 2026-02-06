# app/api/v1/endpoints/pipeline.py

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.db.session import async_session_maker
from app.models.company_profile import CompanyProfile
from app.models.enums import LLMProvider, PipelineStatus
from app.models.expanded_query import ExpandedQuery
from app.models.pipeline_category import PipelineCategory
from app.models.pipeline_job import PipelineJob
from app.models.query_set import QuerySet
from app.models.raw_llm_response import RawLLMResponse
from app.models.user import User
from app.services.llm.factory import LLMFactory
from app.services.pipeline.background_manager import BackgroundJobManager
from app.services.pipeline.category_generator import CategoryGeneratorService
from app.services.pipeline.orchestrator import PipelineOrchestratorService
from app.services.pipeline.query_executor import QueryExecutorService
from app.services.pipeline.query_expander import QueryExpanderService

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


# ============ Schemas ============

class StartPipelineRequest(BaseModel):
    company_profile_id: int
    category_count: int = Field(default=10, ge=1, le=20)
    queries_per_category: int = Field(default=10, ge=1, le=20)
    llm_providers: list[str] = Field(
        default=["gemini", "openai"],
        min_length=1,
        max_length=2,
    )


class StartPipelineResponse(BaseModel):
    job_id: int
    status: str
    message: str
    estimated_queries: int


class PipelineJobStatusResponse(BaseModel):
    id: int
    status: str
    company_profile_id: int
    query_set_id: int  # FIX #6: Reference QuerySet instead of storing config directly
    llm_providers: list[str]
    total_queries: int
    completed_queries: int
    failed_queries: int
    progress_percentage: float
    started_at: datetime | None
    completed_at: datetime | None
    elapsed_seconds: float | None
    error_message: str | None

    class Config:
        from_attributes = True


# FIX #5: Add missing QuerySet-related response schemas
class QuerySetResponse(BaseModel):
    id: int
    name: str
    description: str | None
    category_count: int
    queries_per_category: int
    company_profile_id: int
    created_at: datetime
    job_count: int  # Number of PipelineJobs that used this QuerySet

    class Config:
        from_attributes = True


class QuerySetListResponse(BaseModel):
    query_sets: list[QuerySetResponse]
    total: int


class QuerySetHistoryItem(BaseModel):
    job_id: int
    status: str
    completed_queries: int
    failed_queries: int
    started_at: datetime | None
    completed_at: datetime | None

    class Config:
        from_attributes = True


class QuerySetHistoryResponse(BaseModel):
    query_set_id: int
    query_set_name: str
    executions: list[QuerySetHistoryItem]
    total_executions: int


class PipelineJobSummary(BaseModel):
    id: int
    status: str
    progress_percentage: float
    created_at: datetime

    class Config:
        from_attributes = True


class PipelineJobListResponse(BaseModel):
    jobs: list[PipelineJobSummary]
    total: int


class CancelJobResponse(BaseModel):
    job_id: int
    status: str
    message: str


class CategoryResponse(BaseModel):
    id: int
    name: str
    description: str | None
    llm_provider: str
    persona_type: str
    order_index: int
    query_count: int

    class Config:
        from_attributes = True


class CategoriesListResponse(BaseModel):
    categories: list[CategoryResponse]


class ExpandedQueryResponse(BaseModel):
    id: int
    text: str
    order_index: int
    status: str
    category_id: int
    response_count: int

    class Config:
        from_attributes = True


class QueriesListResponse(BaseModel):
    queries: list[ExpandedQueryResponse]
    total: int


class RawResponseResponse(BaseModel):
    id: int
    content: str
    llm_provider: str
    llm_model: str
    tokens_used: int | None
    latency_ms: float | None
    error_message: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ResponsesListResponse(BaseModel):
    responses: list[RawResponseResponse]


class RerunQuerySetRequest(BaseModel):
    llm_providers: list[str] = Field(
        default=["gemini", "openai"],
        min_length=1,
        max_length=2,
    )


# ============ Endpoints ============

@router.post("/start", response_model=StartPipelineResponse)
async def start_pipeline(
    request: StartPipelineRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Start a new pipeline job for query generation."""
    # Validate company profile
    result = await db.execute(
        select(CompanyProfile).where(
            CompanyProfile.id == request.company_profile_id,
            CompanyProfile.owner_id == current_user.id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found",
        )

    # Validate providers
    valid_providers = {p.value for p in LLMProvider}
    for provider in request.llm_providers:
        if provider not in valid_providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider: {provider}. Valid: {valid_providers}",
            )

    # FIX #1: Create QuerySet FIRST (template for categories/queries)
    query_set = QuerySet(
        name=f"{profile.name} - Query Set {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
        description=f"Auto-generated query set for {profile.name}",
        category_count=request.category_count,
        queries_per_category=request.queries_per_category,
        company_profile_id=profile.id,
        owner_id=current_user.id,
    )
    db.add(query_set)
    await db.commit()
    await db.refresh(query_set)

    # Create PipelineJob referencing QuerySet (execution context)
    job = PipelineJob(
        query_set_id=query_set.id,
        company_profile_id=profile.id,
        owner_id=current_user.id,
        llm_providers=request.llm_providers,
        status=PipelineStatus.PENDING,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Build services
    def _get_api_key(provider: LLMProvider) -> str:
        if provider == LLMProvider.GEMINI:
            return settings.GEMINI_API_KEY
        elif provider == LLMProvider.OPENAI:
            return settings.OPENAI_API_KEY
        raise ValueError(f"Unknown provider: {provider}")

    providers_dict = {
        LLMProvider(p): LLMFactory.create(LLMProvider(p), _get_api_key(LLMProvider(p)))
        for p in request.llm_providers
    }

    category_generators = {
        provider: CategoryGeneratorService(llm)
        for provider, llm in providers_dict.items()
    }
    query_expanders = {
        provider: QueryExpanderService(llm)
        for provider, llm in providers_dict.items()
    }
    query_executor = QueryExecutorService(providers_dict)
    bg_db = async_session_maker()
    orchestrator = PipelineOrchestratorService(
        bg_db, category_generators, query_expanders, query_executor
    )

    # FIX #7: Pass all required arguments to orchestrator.start_pipeline
    try:
        await BackgroundJobManager.start_job(
            job.id,
            orchestrator.start_pipeline(
                job_id=job.id,
                company_profile_id=profile.id,
                query_set_id=query_set.id,
                is_rerun=False,
            ),
        )
    except Exception:
        await bg_db.close()
        raise

    estimated = (
        request.category_count
        * request.queries_per_category
        * len(request.llm_providers)
    )

    return StartPipelineResponse(
        job_id=job.id,
        status=job.status.value,
        message="Pipeline job created and started",
        estimated_queries=estimated,
    )


@router.get("/jobs/{job_id}", response_model=PipelineJobStatusResponse)
async def get_job_status(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get pipeline job status and progress."""
    result = await db.execute(
        select(PipelineJob).where(
            PipelineJob.id == job_id,
            PipelineJob.owner_id == current_user.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    progress = 0.0
    if job.total_queries > 0:
        progress = (
            (job.completed_queries + job.failed_queries) / job.total_queries * 100
        )

    elapsed = None
    if job.started_at:
        end_time = job.completed_at or datetime.utcnow()
        elapsed = (end_time - job.started_at).total_seconds()

    # FIX #6: Return query_set_id instead of category_count/queries_per_category
    # Those fields are on QuerySet now, not PipelineJob
    return PipelineJobStatusResponse(
        id=job.id,
        status=job.status.value,
        company_profile_id=job.company_profile_id,
        query_set_id=job.query_set_id,
        llm_providers=job.llm_providers,
        total_queries=job.total_queries,
        completed_queries=job.completed_queries,
        failed_queries=job.failed_queries,
        progress_percentage=round(progress, 1),
        started_at=job.started_at,
        completed_at=job.completed_at,
        elapsed_seconds=round(elapsed, 1) if elapsed else None,
        error_message=job.error_message,
    )


@router.get("/jobs", response_model=PipelineJobListResponse)
async def list_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    company_profile_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
):
    """List pipeline jobs, optionally filtered by company profile."""
    query = select(PipelineJob).where(PipelineJob.owner_id == current_user.id)

    if company_profile_id:
        query = query.where(PipelineJob.company_profile_id == company_profile_id)

    query = query.order_by(PipelineJob.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    jobs = result.scalars().all()

    # Get total count
    count_query = select(PipelineJob).where(PipelineJob.owner_id == current_user.id)
    if company_profile_id:
        count_query = count_query.where(
            PipelineJob.company_profile_id == company_profile_id
        )
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())

    return PipelineJobListResponse(
        jobs=[
            PipelineJobSummary(
                id=j.id,
                status=j.status.value,
                progress_percentage=(
                    (j.completed_queries + j.failed_queries) / j.total_queries * 100
                    if j.total_queries > 0 else 0
                ),
                created_at=j.created_at,
            )
            for j in jobs
        ],
        total=total,
    )


@router.post("/jobs/{job_id}/cancel", response_model=CancelJobResponse)
async def cancel_job(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Cancel a running pipeline job."""
    result = await db.execute(
        select(PipelineJob).where(
            PipelineJob.id == job_id,
            PipelineJob.owner_id == current_user.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    if job.status in [PipelineStatus.COMPLETED, PipelineStatus.FAILED, PipelineStatus.CANCELLED]:
        return CancelJobResponse(
            job_id=job.id,
            status=job.status.value,
            message="Job already finished",
        )

    cancelled = await BackgroundJobManager.cancel_job(job_id)

    job.status = PipelineStatus.CANCELLED
    job.completed_at = datetime.utcnow()
    await db.commit()

    return CancelJobResponse(
        job_id=job.id,
        status=job.status.value,
        message="Job cancelled successfully" if cancelled else "Job marked as cancelled",
    )


@router.get("/jobs/{job_id}/categories", response_model=CategoriesListResponse)
async def get_categories(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get generated categories for a pipeline job."""
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


@router.get("/jobs/{job_id}/queries", response_model=QueriesListResponse)
async def get_queries(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    category_id: int | None = None,
):
    """Get expanded queries for a pipeline job."""
    # FIX #3: Get job first to access its query_set_id
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

    # FIX #3: Query queries via join through QuerySet
    # ExpandedQuery belongs to PipelineCategory which belongs to QuerySet
    # Path: Job -> QuerySet -> Categories -> ExpandedQueries
    query = (
        select(ExpandedQuery)
        .join(PipelineCategory, ExpandedQuery.category_id == PipelineCategory.id)
        .where(PipelineCategory.query_set_id == job.query_set_id)
        .where(PipelineCategory.llm_provider.in_([LLMProvider(p) for p in job.llm_providers]))
        .options(selectinload(ExpandedQuery.raw_responses))
    )

    if category_id:
        query = query.where(ExpandedQuery.category_id == category_id)

    query = query.order_by(ExpandedQuery.category_id, ExpandedQuery.order_index)

    result = await db.execute(query)
    queries = result.scalars().all()

    return QueriesListResponse(
        queries=[
            ExpandedQueryResponse(
                id=q.id,
                text=q.text,
                order_index=q.order_index,
                status=q.status.value,
                category_id=q.category_id,
                response_count=len(q.raw_responses),
            )
            for q in queries
        ],
        total=len(queries),
    )


@router.get("/queries/{query_id}/responses", response_model=ResponsesListResponse)
async def get_responses(
    query_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get raw LLM responses for a query."""
    # FIX #4: Verify ownership through the correct path
    # ExpandedQuery -> Category -> QuerySet -> owner_id
    # ExpandedQuery has NO direct relationship to PipelineJob
    query_result = await db.execute(
        select(ExpandedQuery)
        .where(ExpandedQuery.id == query_id)
        .options(
            selectinload(ExpandedQuery.category)
            .selectinload(PipelineCategory.query_set)
        )
    )
    query_obj = query_result.scalar_one_or_none()

    # FIX #4: Traverse correct ownership path: query -> category -> query_set -> owner_id
    if not query_obj or query_obj.category.query_set.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found",
        )

    result = await db.execute(
        select(RawLLMResponse)
        .where(RawLLMResponse.query_id == query_id)
        .order_by(RawLLMResponse.created_at)
    )
    responses = result.scalars().all()

    return ResponsesListResponse(
        responses=[
            RawResponseResponse(
                id=r.id,
                content=r.content,
                llm_provider=r.llm_provider.value,
                llm_model=r.llm_model,
                tokens_used=r.tokens_used,
                latency_ms=r.latency_ms,
                error_message=r.error_message,
                created_at=r.created_at,
            )
            for r in responses
        ]
    )


@router.post("/queryset/{query_set_id}/rerun", response_model=StartPipelineResponse)
async def rerun_query_set(
    query_set_id: int,
    request: RerunQuerySetRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Re-run an existing QuerySet to create new time-series data point."""
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
    valid_providers = {p.value for p in LLMProvider}
    for provider in request.llm_providers:
        if provider not in valid_providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider: {provider}. Valid: {valid_providers}",
            )

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
    def _get_api_key(provider: LLMProvider) -> str:
        if provider == LLMProvider.GEMINI:
            return settings.GEMINI_API_KEY
        elif provider == LLMProvider.OPENAI:
            return settings.OPENAI_API_KEY
        raise ValueError(f"Unknown provider: {provider}")

    providers_dict = {
        LLMProvider(p): LLMFactory.create(LLMProvider(p), _get_api_key(LLMProvider(p)))
        for p in request.llm_providers
    }

    category_generators = {
        provider: CategoryGeneratorService(llm)
        for provider, llm in providers_dict.items()
    }
    query_expanders = {
        provider: QueryExpanderService(llm)
        for provider, llm in providers_dict.items()
    }
    query_executor = QueryExecutorService(providers_dict)
    bg_db = async_session_maker()
    orchestrator = PipelineOrchestratorService(
        bg_db, category_generators, query_expanders, query_executor
    )

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
        status=job.status.value,
        message="Re-run pipeline job created and started",
        estimated_queries=estimated,
    )


@router.get("/queryset/{query_set_id}/history", response_model=QuerySetHistoryResponse)
async def get_query_set_history(
    query_set_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get execution history for a QuerySet (for time-series analysis)."""
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
                status=j.status.value,
                completed_queries=j.completed_queries,
                failed_queries=j.failed_queries,
                started_at=j.started_at,
                completed_at=j.completed_at,
            )
            for j in jobs
        ],
        total_executions=len(jobs),
    )


@router.get("/queryset", response_model=QuerySetListResponse)
async def list_query_sets(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    company_profile_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
):
    """List all QuerySets owned by user."""
    query = select(QuerySet).where(QuerySet.owner_id == current_user.id)

    if company_profile_id:
        query = query.where(QuerySet.company_profile_id == company_profile_id)

    query = query.order_by(QuerySet.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query.options(selectinload(QuerySet.pipeline_jobs)))
    query_sets = result.scalars().all()

    # Get total count
    count_query = select(QuerySet).where(QuerySet.owner_id == current_user.id)
    if company_profile_id:
        count_query = count_query.where(QuerySet.company_profile_id == company_profile_id)
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())

    return QuerySetListResponse(
        query_sets=[
            QuerySetResponse(
                id=qs.id,
                name=qs.name,
                description=qs.description,
                category_count=qs.category_count,
                queries_per_category=qs.queries_per_category,
                company_profile_id=qs.company_profile_id,
                created_at=qs.created_at,
                job_count=len(qs.pipeline_jobs),
            )
            for qs in query_sets
        ],
        total=total,
    )
