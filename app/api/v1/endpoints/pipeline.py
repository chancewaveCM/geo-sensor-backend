# app/api/v1/endpoints/pipeline.py

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
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
from app.models.schedule_config import ScheduleConfig
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
    last_job_status: str | None = None
    last_run_at: datetime | None = None
    total_responses: int = 0

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
    company_profile_id: int
    company_name: str | None = None
    query_set_id: int | None = None
    query_set_name: str | None = None
    llm_providers: list[str]
    total_queries: int
    completed_queries: int
    failed_queries: int
    progress_percentage: float
    started_at: datetime | None
    completed_at: datetime | None
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


class CompanyProfilePipelineStats(BaseModel):
    company_profile_id: int
    company_name: str
    total_query_sets: int
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    success_rate_30d: float  # percentage 0-100
    last_run_status: str | None  # most recent job status
    last_run_at: datetime | None  # most recent job started_at
    avg_processing_time_seconds: float | None  # avg of completed jobs
    data_freshness_hours: float | None  # hours since last successful completion
    health_grade: str  # "green", "yellow", "red"

    class Config:
        from_attributes = True


class ProfileStatsListResponse(BaseModel):
    profiles: list[CompanyProfilePipelineStats]
    total: int


class RerunQuerySetRequest(BaseModel):
    llm_providers: list[str] = Field(
        default=["gemini", "openai"],
        min_length=1,
        max_length=2,
    )


class UpdateCategoryRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class CreateCategoryRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    persona_type: str = Field(default="consumer")
    llm_provider: str = Field(default="gemini")
    order_index: int = Field(default=0, ge=0)


class QuerySetDetailCategoryItem(BaseModel):
    id: int
    name: str
    description: str | None
    llm_provider: str
    persona_type: str
    order_index: int
    query_count: int

    class Config:
        from_attributes = True


class QuerySetDetailJobItem(BaseModel):
    id: int
    status: str
    llm_providers: list[str]
    total_queries: int
    completed_queries: int
    failed_queries: int
    started_at: datetime | None
    completed_at: datetime | None

    class Config:
        from_attributes = True


class QuerySetDetailResponse(BaseModel):
    id: int
    name: str
    description: str | None
    category_count: int
    queries_per_category: int
    company_profile_id: int
    created_at: datetime
    categories: list[QuerySetDetailCategoryItem]
    last_job: QuerySetDetailJobItem | None
    total_jobs: int
    total_responses: int

    class Config:
        from_attributes = True


class CreateScheduleRequest(BaseModel):
    query_set_id: int
    interval_minutes: int = Field(..., ge=60, le=43200, description="60 min to 30 days")
    llm_providers: list[str] = Field(
        default=["gemini", "openai"],
        min_length=1,
        max_length=2,
    )
    is_active: bool = True


class UpdateScheduleRequest(BaseModel):
    interval_minutes: int | None = Field(default=None, ge=60, le=43200)
    llm_providers: list[str] | None = Field(default=None, min_length=1, max_length=2)
    is_active: bool | None = None


class ScheduleConfigResponse(BaseModel):
    id: int
    query_set_id: int
    query_set_name: str
    company_profile_id: int
    company_name: str
    interval_minutes: int
    is_active: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    llm_providers: list[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ScheduleListResponse(BaseModel):
    schedules: list[ScheduleConfigResponse]
    total: int


# ============ Helpers ============


def _calculate_health_grade(
    success_rate_30d: float,
    data_freshness_hours: float | None,
    consecutive_failures: int,
    total_query_sets: int,
) -> Literal["green", "yellow", "red"]:
    """Calculate health grade based on KPI rules."""
    if (
        success_rate_30d < 60
        or (data_freshness_hours is not None and data_freshness_hours >= 72)
        or consecutive_failures >= 3
        or total_query_sets == 0
    ):
        return "red"
    if (
        success_rate_30d < 90
        or (data_freshness_hours is not None and 24 <= data_freshness_hours < 72)
    ):
        return "yellow"
    return "green"


def _validate_llm_providers(providers: list[str]) -> None:
    """Validate that all provider strings are valid LLMProvider values."""
    valid_providers = {p.value for p in LLMProvider}
    for provider in providers:
        if provider not in valid_providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider: {provider}. Valid: {valid_providers}",
            )


def _build_pipeline_services(
    llm_providers: list[str],
) -> tuple[PipelineOrchestratorService, AsyncSession]:
    """Build pipeline orchestrator with all required services.

    Returns (orchestrator, bg_db) - caller must close bg_db on error.
    """
    def _get_api_key(provider: LLMProvider) -> str:
        if provider == LLMProvider.GEMINI:
            return settings.GEMINI_API_KEY
        elif provider == LLMProvider.OPENAI:
            return settings.OPENAI_API_KEY
        raise ValueError(f"Unknown provider: {provider}")

    providers_dict = {
        LLMProvider(p): LLMFactory.create(LLMProvider(p), _get_api_key(LLMProvider(p)))
        for p in llm_providers
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
    return orchestrator, bg_db


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
    _validate_llm_providers(request.llm_providers)

    # FIX #1: Create QuerySet FIRST (template for categories/queries)
    query_set = QuerySet(
        name=f"{profile.name} - Query Set {datetime.now(tz=UTC).strftime('%Y-%m-%d %H:%M')}",
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
    orchestrator, bg_db = _build_pipeline_services(request.llm_providers)

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
        status=job.status,
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
        # SQLite stores naive datetimes, so use naive UTC now to avoid mismatch
        end_time = job.completed_at or datetime.now(tz=UTC).replace(tzinfo=None)
        started = job.started_at.replace(tzinfo=None) if job.started_at.tzinfo else job.started_at
        elapsed = (end_time - started).total_seconds()

    # FIX #6: Return query_set_id instead of category_count/queries_per_category
    # Those fields are on QuerySet now, not PipelineJob
    return PipelineJobStatusResponse(
        id=job.id,
        status=job.status,
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

    query = (
        query.order_by(PipelineJob.created_at.desc())
        .offset(offset)
        .limit(limit)
        .options(
            selectinload(PipelineJob.company_profile),
            selectinload(PipelineJob.query_set),
        )
    )

    result = await db.execute(query)
    jobs = result.scalars().all()

    # Get total count
    count_query = select(func.count(PipelineJob.id)).where(PipelineJob.owner_id == current_user.id)
    if company_profile_id:
        count_query = count_query.where(
            PipelineJob.company_profile_id == company_profile_id
        )
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return PipelineJobListResponse(
        jobs=[
            PipelineJobSummary(
                id=j.id,
                status=j.status,
                company_profile_id=j.company_profile_id,
                company_name=j.company_profile.name if j.company_profile else None,
                query_set_id=j.query_set_id,
                query_set_name=j.query_set.name if j.query_set else None,
                llm_providers=j.llm_providers,
                total_queries=j.total_queries,
                completed_queries=j.completed_queries,
                failed_queries=j.failed_queries,
                progress_percentage=(
                    (j.completed_queries + j.failed_queries) / j.total_queries * 100
                    if j.total_queries > 0 else 0
                ),
                started_at=j.started_at,
                completed_at=j.completed_at,
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
            status=job.status,
            message="Job already finished",
        )

    cancelled = await BackgroundJobManager.cancel_job(job_id)

    job.status = PipelineStatus.CANCELLED
    job.completed_at = datetime.now(tz=UTC)
    await db.commit()

    return CancelJobResponse(
        job_id=job.id,
        status=job.status,
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
                status=q.status,
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


@router.get("/queryset", response_model=QuerySetListResponse)
async def list_query_sets(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    company_profile_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
):
    """List all QuerySets owned by user."""
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
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get detailed information about a QuerySet including categories and job history."""
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


@router.put("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    request: UpdateCategoryRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Partially update a category."""
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
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Delete a category (cascade deletes expanded queries)."""
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


@router.post("/queryset/{query_set_id}/categories", response_model=CategoryResponse)
async def create_category(
    query_set_id: int,
    request: CreateCategoryRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a new category for a query set."""
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


@router.get("/categories/{category_id}/queries", response_model=QueriesListResponse)
async def get_category_queries(
    category_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get expanded queries for a category."""
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


@router.get("/profiles/stats", response_model=ProfileStatsListResponse)
async def get_profile_pipeline_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get pipeline health statistics for each company profile.

    Optimized from 8 queries to 3:
    1. Profiles + QuerySet counts (LEFT JOIN + GROUP BY)
    2. Combined job statistics (all-time, 30-day, last runs, avg time)
    3. Recent 3 jobs for consecutive failures (window function)

    SQLite-compatible (uses julianday). For PostgreSQL, replace with EXTRACT(EPOCH ...).
    """
    now = datetime.now(tz=UTC)
    thirty_days_ago = now - timedelta(days=30)

    # QUERY 1: Get profiles with QuerySet counts in a single query (LEFT JOIN)
    qs_count_subq = (
        select(
            QuerySet.company_profile_id,
            func.count(QuerySet.id).label("total_query_sets"),
        )
        .where(QuerySet.owner_id == current_user.id)
        .group_by(QuerySet.company_profile_id)
        .subquery()
    )

    profiles_result = await db.execute(
        select(
            CompanyProfile,
            func.coalesce(qs_count_subq.c.total_query_sets, 0).label("total_query_sets"),
        )
        .outerjoin(qs_count_subq, CompanyProfile.id == qs_count_subq.c.company_profile_id)
        .where(CompanyProfile.owner_id == current_user.id)
    )
    profile_rows = profiles_result.all()

    if not profile_rows:
        return ProfileStatsListResponse(profiles=[], total=0)

    profile_ids = [row.CompanyProfile.id for row in profile_rows]

    # QUERY 2: Mega-aggregated job statistics (combines 5 previous queries)
    # All-time stats, 30-day stats, last success timestamp, and avg processing time
    job_aggregates = (
        select(
            PipelineJob.company_profile_id,
            # All-time totals
            func.count(PipelineJob.id).label("total_jobs"),
            func.sum(
                case((PipelineJob.status == PipelineStatus.COMPLETED, 1), else_=0)
            ).label("completed_jobs"),
            func.sum(
                case((PipelineJob.status == PipelineStatus.FAILED, 1), else_=0)
            ).label("failed_jobs"),
            # 30-day success rate numerator and denominator
            func.sum(
                case(
                    (
                        (PipelineJob.status.in_([
                            PipelineStatus.COMPLETED,
                            PipelineStatus.FAILED
                        ]))
                        & (PipelineJob.created_at >= thirty_days_ago),
                        1,
                    ),
                    else_=0,
                )
            ).label("recent_total"),
            func.sum(
                case(
                    (
                        (PipelineJob.status == PipelineStatus.COMPLETED)
                        & (PipelineJob.created_at >= thirty_days_ago),
                        1,
                    ),
                    else_=0,
                )
            ).label("recent_completed"),
            # Last successful completion timestamp (for data freshness)
            func.max(
                case((
                    PipelineJob.status == PipelineStatus.COMPLETED,
                    PipelineJob.completed_at
                ))
            ).label("last_success_completed_at"),
            # Average processing time (SQLite julianday, PostgreSQL: EXTRACT(EPOCH ...))
            func.avg(
                case(
                    (
                        (PipelineJob.status == PipelineStatus.COMPLETED)
                        & (PipelineJob.started_at.isnot(None))
                        & (PipelineJob.completed_at.isnot(None)),
                        func.julianday(PipelineJob.completed_at)
                        - func.julianday(PipelineJob.started_at),
                    )
                )
            ).label("avg_days"),
        )
        .where(
            PipelineJob.company_profile_id.in_(profile_ids),
            PipelineJob.owner_id == current_user.id,
        )
        .group_by(PipelineJob.company_profile_id)
    )
    job_stats_result = await db.execute(job_aggregates)
    job_stats_map = {row.company_profile_id: row for row in job_stats_result.all()}

    # QUERY 3: Last job info + consecutive failures (recent 3 jobs per profile)
    jobs_window_subq = (
        select(
            PipelineJob.company_profile_id,
            PipelineJob.status,
            PipelineJob.started_at,
            func.row_number()
            .over(
                partition_by=PipelineJob.company_profile_id,
                order_by=PipelineJob.created_at.desc()
            )
            .label("rn"),
        )
        .where(
            PipelineJob.company_profile_id.in_(profile_ids),
            PipelineJob.owner_id == current_user.id,
        )
        .subquery()
    )

    jobs_window_result = await db.execute(
        select(jobs_window_subq).where(jobs_window_subq.c.rn <= 3)
    )

    # Build maps from window results (last job + consecutive failures)
    last_job_map: dict[int, any] = {}
    consecutive_failures_map: dict[int, int] = {}
    profile_recent_jobs: dict[int, list] = {}

    for row in jobs_window_result.all():
        pid = row.company_profile_id

        # First row (rn=1) is the most recent job
        if row.rn == 1:
            last_job_map[pid] = row

        # Collect statuses for consecutive failure calculation
        profile_recent_jobs.setdefault(pid, []).append(row.status)

    # Calculate consecutive failures (count from most recent until first non-failure)
    for pid, statuses in profile_recent_jobs.items():
        count = 0
        for s in statuses:
            if s == PipelineStatus.FAILED or s == PipelineStatus.FAILED.value:
                count += 1
            else:
                break
        consecutive_failures_map[pid] = count

    # Build response from collected data (Python-side aggregation)
    stats_list = []
    for row in profile_rows:
        profile = row.CompanyProfile
        pid = profile.id

        # Extract from combined job stats
        job_stats = job_stats_map.get(pid)
        total_jobs = job_stats.total_jobs if job_stats else 0
        completed_jobs = job_stats.completed_jobs if job_stats else 0
        failed_jobs = job_stats.failed_jobs if job_stats else 0

        # 30-day success rate
        success_rate_30d = 0.0
        if job_stats and job_stats.recent_total:
            success_rate_30d = (job_stats.recent_completed or 0) / job_stats.recent_total * 100

        # Last job status and timestamp
        last_job = last_job_map.get(pid)
        last_run_status = None
        last_run_at = None
        if last_job:
            last_run_status = last_job.status
            last_run_at = last_job.started_at

        # Data freshness from aggregated last success timestamp
        data_freshness_hours = None
        if job_stats and job_stats.last_success_completed_at:
            data_freshness_hours = (
                now - job_stats.last_success_completed_at
            ).total_seconds() / 3600

        # Average processing time (convert days to seconds)
        avg_processing_time = None
        if job_stats and job_stats.avg_days:
            avg_processing_time = job_stats.avg_days * 86400

        # Query sets from joined query
        total_query_sets = row.total_query_sets or 0

        # Consecutive failures
        consecutive_failures = consecutive_failures_map.get(pid, 0)

        health_grade = _calculate_health_grade(
            success_rate_30d, data_freshness_hours,
            consecutive_failures, total_query_sets,
        )

        stats_list.append(CompanyProfilePipelineStats(
            company_profile_id=pid,
            company_name=profile.name,
            total_query_sets=total_query_sets,
            total_jobs=total_jobs,
            completed_jobs=completed_jobs,
            failed_jobs=failed_jobs,
            success_rate_30d=round(success_rate_30d, 1),
            last_run_status=last_run_status,
            last_run_at=last_run_at,
            avg_processing_time_seconds=(
                round(avg_processing_time, 1)
                if avg_processing_time else None
            ),
            data_freshness_hours=(
                round(data_freshness_hours, 1)
                if data_freshness_hours else None
            ),
            health_grade=health_grade,
        ))

    return ProfileStatsListResponse(profiles=stats_list, total=len(stats_list))


@router.post(
    "/schedules",
    response_model=ScheduleConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule(
    request: CreateScheduleRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a pipeline schedule for a QuerySet."""
    # Verify QuerySet ownership
    qs_result = await db.execute(
        select(QuerySet)
        .where(
            QuerySet.id == request.query_set_id,
            QuerySet.owner_id == current_user.id,
        )
        .options(selectinload(QuerySet.company_profile))
    )
    query_set = qs_result.scalar_one_or_none()
    if not query_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QuerySet not found",
        )

    # Check for duplicate (unique constraint on query_set_id)
    existing = await db.execute(
        select(ScheduleConfig).where(
            ScheduleConfig.query_set_id == request.query_set_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A schedule already exists for this QuerySet",
        )

    # Validate providers
    _validate_llm_providers(request.llm_providers)

    # Calculate next_run_at
    now = datetime.now(tz=UTC)
    next_run = now + timedelta(minutes=request.interval_minutes)

    schedule = ScheduleConfig(
        query_set_id=request.query_set_id,
        interval_minutes=request.interval_minutes,
        is_active=request.is_active,
        llm_providers=request.llm_providers,
        next_run_at=next_run,
        owner_id=current_user.id,
    )
    db.add(schedule)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A schedule already exists for this QuerySet",
        )
    await db.refresh(schedule)

    return ScheduleConfigResponse(
        id=schedule.id,
        query_set_id=schedule.query_set_id,
        query_set_name=query_set.name,
        company_profile_id=query_set.company_profile_id,
        company_name=query_set.company_profile.name,
        interval_minutes=schedule.interval_minutes,
        is_active=schedule.is_active,
        last_run_at=schedule.last_run_at,
        next_run_at=schedule.next_run_at,
        llm_providers=schedule.llm_providers,
        created_at=schedule.created_at,
    )


@router.get("/schedules", response_model=ScheduleListResponse)
async def list_schedules(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    query_set_id: int | None = None,
    company_profile_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
):
    """List all pipeline schedules for the current user."""
    query = select(ScheduleConfig).where(ScheduleConfig.owner_id == current_user.id)
    count_query = select(func.count(ScheduleConfig.id)).where(
        ScheduleConfig.owner_id == current_user.id
    )

    if query_set_id is not None:
        query = query.where(ScheduleConfig.query_set_id == query_set_id)
        count_query = count_query.where(ScheduleConfig.query_set_id == query_set_id)

    if company_profile_id is not None:
        query = (
            query
            .join(QuerySet, ScheduleConfig.query_set_id == QuerySet.id)
            .where(QuerySet.company_profile_id == company_profile_id)
        )
        count_query = (
            count_query
            .join(QuerySet, ScheduleConfig.query_set_id == QuerySet.id)
            .where(QuerySet.company_profile_id == company_profile_id)
        )

    result = await db.execute(
        query
        .order_by(ScheduleConfig.created_at.desc())
        .offset(offset)
        .limit(limit)
        .options(
            selectinload(ScheduleConfig.query_set).selectinload(
                QuerySet.company_profile
            )
        )
    )
    schedules = result.scalars().all()

    # Get total count
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return ScheduleListResponse(
        schedules=[
            ScheduleConfigResponse(
                id=s.id,
                query_set_id=s.query_set_id,
                query_set_name=s.query_set.name,
                company_profile_id=s.query_set.company_profile_id,
                company_name=s.query_set.company_profile.name,
                interval_minutes=s.interval_minutes,
                is_active=s.is_active,
                last_run_at=s.last_run_at,
                next_run_at=s.next_run_at,
                llm_providers=s.llm_providers,
                created_at=s.created_at,
            )
            for s in schedules
        ],
        total=total,
    )


@router.put("/schedules/{schedule_id}", response_model=ScheduleConfigResponse)
async def update_schedule(
    schedule_id: int,
    request: UpdateScheduleRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Update a pipeline schedule."""
    result = await db.execute(
        select(ScheduleConfig)
        .where(
            ScheduleConfig.id == schedule_id,
            ScheduleConfig.owner_id == current_user.id,
        )
        .options(
            selectinload(ScheduleConfig.query_set).selectinload(
                QuerySet.company_profile
            )
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )

    if request.interval_minutes is not None:
        schedule.interval_minutes = request.interval_minutes
        # Policy: Always calculate next_run_at as current time + new interval.
        # This ensures users see immediate effect when changing interval.
        now = datetime.now(tz=UTC)
        schedule.next_run_at = now + timedelta(
            minutes=request.interval_minutes
        )

    if request.llm_providers is not None:
        _validate_llm_providers(request.llm_providers)
        schedule.llm_providers = request.llm_providers

    if request.is_active is not None:
        schedule.is_active = request.is_active

    await db.commit()
    await db.refresh(schedule)

    return ScheduleConfigResponse(
        id=schedule.id,
        query_set_id=schedule.query_set_id,
        query_set_name=schedule.query_set.name,
        company_profile_id=schedule.query_set.company_profile_id,
        company_name=schedule.query_set.company_profile.name,
        interval_minutes=schedule.interval_minutes,
        is_active=schedule.is_active,
        last_run_at=schedule.last_run_at,
        next_run_at=schedule.next_run_at,
        llm_providers=schedule.llm_providers,
        created_at=schedule.created_at,
    )


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Delete a pipeline schedule."""
    result = await db.execute(
        select(ScheduleConfig).where(
            ScheduleConfig.id == schedule_id,
            ScheduleConfig.owner_id == current_user.id,
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )

    await db.delete(schedule)
    await db.commit()

    return {"message": "Schedule deleted"}
