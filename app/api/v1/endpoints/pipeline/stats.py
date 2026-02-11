# app/api/v1/endpoints/pipeline/stats.py

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import case, func, select

from app.api.deps import DbSession, get_current_user
from app.models.company_profile import CompanyProfile
from app.models.enums import PipelineStatus
from app.models.pipeline_job import PipelineJob
from app.models.query_set import QuerySet
from app.models.user import User
from app.schemas.pipeline import (
    CompanyProfilePipelineStats,
    ProfileStatsListResponse,
)

from ._common import _add_sunset_headers, _calculate_health_grade

router = APIRouter()


@router.get("/profiles/stats", response_model=ProfileStatsListResponse)
async def get_profile_pipeline_stats(
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
):
    """Get pipeline health statistics for each company profile.

    Optimized from 8 queries to 3:
    1. Profiles + QuerySet counts (LEFT JOIN + GROUP BY)
    2. Combined job statistics (all-time, 30-day, last runs, avg time)
    3. Recent 3 jobs for consecutive failures (window function)

    SQLite-compatible (uses julianday). For PostgreSQL, replace with EXTRACT(EPOCH ...).
    """
    _add_sunset_headers(response)
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
