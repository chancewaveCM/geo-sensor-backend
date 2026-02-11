"""Unified Analysis endpoints.

New analysis API that wraps PipelineJob with mode='quick'|'advanced'.
Replaces the old generated-queries + pipeline two-step workflow.
"""

import logging
import time
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, get_current_active_user
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
from app.schemas.unified_analysis import (
    AnalysisJobListResponse,
    AnalysisJobResponse,
    DeleteAnalysisResponse,
    QueryResponse,
    RerunQueryRequest,
    RerunQueryResponse,
    StartAnalysisRequest,
    StartAnalysisResponse,
    UpdateQueryRequest,
)
from app.services.llm.factory import LLMFactory
from app.services.pipeline.background_manager import BackgroundJobManager
from app.services.pipeline.category_generator import CategoryGeneratorService
from app.services.pipeline.orchestrator import PipelineOrchestratorService
from app.services.pipeline.query_executor import QueryExecutorService
from app.services.pipeline.query_expander import QueryExpanderService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/unified-analysis", tags=["unified-analysis"])


def _validate_llm_providers(providers: list[str]) -> None:
    """Validate that all provider strings are valid LLMProvider values."""
    valid_providers = {p.value for p in LLMProvider}
    for provider in providers:
        if provider not in valid_providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid provider: {provider}. "
                    f"Valid: {valid_providers}"
                ),
            )


def _build_pipeline_services(
    llm_providers: list[str],
) -> tuple[PipelineOrchestratorService, AsyncSession]:
    """Build pipeline orchestrator with all required services."""
    def _get_api_key(provider: LLMProvider) -> str:
        if provider == LLMProvider.GEMINI:
            return settings.GEMINI_API_KEY
        elif provider == LLMProvider.OPENAI:
            return settings.OPENAI_API_KEY
        raise ValueError(f"Unknown provider: {provider}")

    providers_dict = {
        LLMProvider(p): LLMFactory.create(
            LLMProvider(p), _get_api_key(LLMProvider(p))
        )
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


@router.post("/start", response_model=StartAnalysisResponse)
async def start_analysis(
    request: StartAnalysisRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Start a new unified analysis job.

    Quick mode: 3 categories, 10 queries per category.
    Advanced mode: User-configured category_count and queries_per_category.
    """
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

    _validate_llm_providers(request.llm_providers)

    # Determine config based on mode
    if request.mode == "quick":
        category_count = 3
        queries_per_category = 10
    else:  # advanced
        category_count = request.category_count or 10
        queries_per_category = request.queries_per_category or 10

    # Create QuerySet
    timestamp = datetime.now(tz=UTC).strftime('%Y-%m-%d %H:%M')
    query_set = QuerySet(
        name=(
            f"{profile.name} - {request.mode.title()} "
            f"Analysis {timestamp}"
        ),
        description=f"{request.mode.title()} analysis for {profile.name}",
        category_count=category_count,
        queries_per_category=queries_per_category,
        company_profile_id=profile.id,
        owner_id=current_user.id,
    )
    db.add(query_set)
    await db.commit()
    await db.refresh(query_set)

    # Create PipelineJob with mode
    job = PipelineJob(
        query_set_id=query_set.id,
        company_profile_id=profile.id,
        owner_id=current_user.id,
        llm_providers=request.llm_providers,
        status=PipelineStatus.PENDING,
        mode=request.mode,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Build services and start background job
    orchestrator, bg_db = _build_pipeline_services(request.llm_providers)
    try:
        async def _run_with_cleanup():
            try:
                await orchestrator.start_pipeline(
                    job_id=job.id,
                    company_profile_id=profile.id,
                    query_set_id=query_set.id,
                    is_rerun=False,
                )
            finally:
                await bg_db.close()

        await BackgroundJobManager.start_job(
            job.id,
            _run_with_cleanup(),
        )
    except Exception:
        await bg_db.close()
        raise

    estimated = (
        category_count * queries_per_category * len(request.llm_providers)
    )

    return StartAnalysisResponse(
        job_id=job.id,
        mode=request.mode,
        status=job.status,
        message=f"{request.mode.title()} analysis started",
        estimated_queries=estimated,
    )


@router.get("/jobs", response_model=AnalysisJobListResponse)
async def list_analysis_jobs(
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
    mode: str | None = None,
    company_profile_id: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List unified analysis jobs (mode='quick' or 'advanced')."""
    query = select(PipelineJob).where(
        PipelineJob.owner_id == current_user.id,
        PipelineJob.mode.in_(["quick", "advanced"]),
    )

    if mode:
        query = query.where(PipelineJob.mode == mode)
    if company_profile_id:
        query = query.where(
            PipelineJob.company_profile_id == company_profile_id
        )

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

    # Count
    count_query = select(func.count(PipelineJob.id)).where(
        PipelineJob.owner_id == current_user.id,
        PipelineJob.mode.in_(["quick", "advanced"]),
    )
    if mode:
        count_query = count_query.where(PipelineJob.mode == mode)
    if company_profile_id:
        count_query = count_query.where(
            PipelineJob.company_profile_id == company_profile_id
        )
    total = (await db.execute(count_query)).scalar() or 0

    return AnalysisJobListResponse(
        jobs=[
            AnalysisJobResponse(
                id=j.id,
                mode=j.mode,
                status=j.status,
                company_profile_id=j.company_profile_id,
                company_name=(
                    j.company_profile.name if j.company_profile else None
                ),
                query_set_id=j.query_set_id,
                query_set_name=j.query_set.name if j.query_set else None,
                llm_providers=j.llm_providers,
                total_queries=j.total_queries,
                completed_queries=j.completed_queries,
                failed_queries=j.failed_queries,
                progress_percentage=(
                    (j.completed_queries + j.failed_queries)
                    / j.total_queries
                    * 100
                    if j.total_queries > 0
                    else 0
                ),
                started_at=j.started_at,
                completed_at=j.completed_at,
                created_at=j.created_at,
                error_message=j.error_message,
            )
            for j in jobs
        ],
        total=total,
    )


@router.get("/jobs/{job_id}", response_model=AnalysisJobResponse)
async def get_analysis_job(
    job_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get details of a specific analysis job."""
    result = await db.execute(
        select(PipelineJob)
        .where(
            PipelineJob.id == job_id,
            PipelineJob.owner_id == current_user.id,
            PipelineJob.mode.in_(["quick", "advanced"]),
        )
        .options(
            selectinload(PipelineJob.company_profile),
            selectinload(PipelineJob.query_set),
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis job not found",
        )

    return AnalysisJobResponse(
        id=job.id,
        mode=job.mode,
        status=job.status,
        company_profile_id=job.company_profile_id,
        company_name=job.company_profile.name if job.company_profile else None,
        query_set_id=job.query_set_id,
        query_set_name=job.query_set.name if job.query_set else None,
        llm_providers=job.llm_providers,
        total_queries=job.total_queries,
        completed_queries=job.completed_queries,
        failed_queries=job.failed_queries,
        progress_percentage=(
            (job.completed_queries + job.failed_queries)
            / job.total_queries
            * 100
            if job.total_queries > 0
            else 0
        ),
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
        error_message=job.error_message,
    )


@router.delete("/jobs/{job_id}", response_model=DeleteAnalysisResponse)
async def delete_analysis_job(
    job_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Cancel a running analysis job or delete a completed one."""
    result = await db.execute(
        select(PipelineJob).where(
            PipelineJob.id == job_id,
            PipelineJob.owner_id == current_user.id,
            PipelineJob.mode.in_(["quick", "advanced"]),
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis job not found",
        )

    if job.status in [PipelineStatus.PENDING, PipelineStatus.RUNNING]:
        # Cancel running job
        await BackgroundJobManager.cancel_job(job_id)
        job.status = PipelineStatus.CANCELLED
        job.completed_at = datetime.now(tz=UTC)
        await db.commit()
        return DeleteAnalysisResponse(
            job_id=job.id,
            status=job.status,
            message="Analysis job cancelled",
        )

    # For completed/failed/cancelled jobs, just acknowledge
    return DeleteAnalysisResponse(
        job_id=job.id,
        status=job.status,
        message="Analysis job already finished",
    )


@router.put("/queries/{query_id}", response_model=QueryResponse)
async def update_query_text(
    query_id: int,
    request: UpdateQueryRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Update the text of an expanded query."""
    # Verify ownership through: query -> category -> query_set -> owner
    result = await db.execute(
        select(ExpandedQuery)
        .where(ExpandedQuery.id == query_id)
        .options(
            selectinload(ExpandedQuery.category)
            .selectinload(PipelineCategory.query_set)
        )
    )
    query = result.scalar_one_or_none()
    if not query or query.category.query_set.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found",
        )

    query.text = request.text
    await db.commit()
    await db.refresh(query)

    return QueryResponse(
        id=query.id,
        text=query.text,
        order_index=query.order_index,
        status=query.status,
        category_id=query.category_id,
    )


@router.post("/queries/{query_id}/rerun", response_model=RerunQueryResponse)
async def rerun_query(
    query_id: int,
    request: RerunQueryRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Rerun a specific query against selected LLM providers.

    Deletes existing responses for the query and re-executes it.
    """
    _validate_llm_providers(request.llm_providers)

    # Verify ownership
    result = await db.execute(
        select(ExpandedQuery)
        .where(ExpandedQuery.id == query_id)
        .options(
            selectinload(ExpandedQuery.category)
            .selectinload(PipelineCategory.query_set),
            selectinload(ExpandedQuery.raw_responses),
        )
    )
    query = result.scalar_one_or_none()
    if not query or query.category.query_set.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found",
        )

    # Collect old response IDs but don't delete yet
    old_response_ids = [resp.id for resp in query.raw_responses]

    # Re-execute the query
    def _get_api_key(provider: LLMProvider) -> str:
        if provider == LLMProvider.GEMINI:
            return settings.GEMINI_API_KEY
        elif provider == LLMProvider.OPENAI:
            return settings.OPENAI_API_KEY
        raise ValueError(f"Unknown provider: {provider}")

    for provider_str in request.llm_providers:
        provider = LLMProvider(provider_str)
        llm = LLMFactory.create(provider, _get_api_key(provider))
        try:
            start_time = time.time()
            response = await llm.generate(query.text, max_tokens=2048)
            latency = (time.time() - start_time) * 1000

            raw_response = RawLLMResponse(
                query_id=query.id,
                pipeline_job_id=None,
                content=response.content,
                llm_provider=provider,
                llm_model=getattr(response, 'model', provider_str),
                tokens_used=getattr(response, 'tokens_used', None),
                latency_ms=latency,
            )
            db.add(raw_response)
        except Exception as e:
            logger.warning(f"Rerun failed for provider {provider_str}: {e}")
            raw_response = RawLLMResponse(
                query_id=query.id,
                pipeline_job_id=None,
                content="",
                llm_provider=provider,
                llm_model=provider_str,
                error_message=str(e),
            )
            db.add(raw_response)

    # Delete old responses after successful new ones
    for resp_id in old_response_ids:
        old_resp = await db.get(RawLLMResponse, resp_id)
        if old_resp:
            await db.delete(old_resp)

    query.status = "completed"
    await db.commit()

    return RerunQueryResponse(
        query_id=query.id,
        status="completed",
        message=f"Query rerun against {len(request.llm_providers)} provider(s)",
    )
