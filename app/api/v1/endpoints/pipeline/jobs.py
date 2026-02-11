# app/api/v1/endpoints/pipeline/jobs.py

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, get_current_user
from app.models.company_profile import CompanyProfile
from app.models.enums import PipelineStatus
from app.models.pipeline_job import PipelineJob
from app.models.query_set import QuerySet
from app.models.user import User
from app.schemas.pipeline import (
    CancelJobResponse,
    PipelineJobListResponse,
    PipelineJobStatusResponse,
    PipelineJobSummary,
    StartPipelineRequest,
    StartPipelineResponse,
)
from app.services.pipeline.background_manager import BackgroundJobManager

from ._common import _add_sunset_headers, _build_pipeline_services, _validate_llm_providers

router = APIRouter()


@router.post("/start", response_model=StartPipelineResponse)
async def start_pipeline(
    request: StartPipelineRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
):
    """Start a new pipeline job for query generation."""
    _add_sunset_headers(response)
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
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
):
    """Get pipeline job status and progress."""
    _add_sunset_headers(response)
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
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
    company_profile_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
):
    """List pipeline jobs, optionally filtered by company profile."""
    _add_sunset_headers(response)
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
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
):
    """Cancel a running pipeline job."""
    _add_sunset_headers(response)
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
