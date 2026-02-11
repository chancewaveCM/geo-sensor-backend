# app/api/v1/endpoints/pipeline/schedules.py

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, get_current_user
from app.models.query_set import QuerySet
from app.models.schedule_config import ScheduleConfig
from app.models.user import User
from app.schemas.pipeline import (
    CreateScheduleRequest,
    ScheduleConfigResponse,
    ScheduleListResponse,
    UpdateScheduleRequest,
)

from ._common import _add_sunset_headers, _validate_llm_providers

router = APIRouter()


@router.post(
    "/schedules",
    response_model=ScheduleConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule(
    request: CreateScheduleRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
):
    """Create a pipeline schedule for a QuerySet."""
    _add_sunset_headers(response)
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
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
    query_set_id: int | None = None,
    company_profile_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
):
    """List all pipeline schedules for the current user."""
    _add_sunset_headers(response)
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
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
):
    """Update a pipeline schedule."""
    _add_sunset_headers(response)
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
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
):
    """Delete a pipeline schedule."""
    _add_sunset_headers(response)
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
