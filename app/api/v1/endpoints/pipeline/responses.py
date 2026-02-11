# app/api/v1/endpoints/pipeline/responses.py

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, get_current_user
from app.models.enums import LLMProvider
from app.models.expanded_query import ExpandedQuery
from app.models.pipeline_category import PipelineCategory
from app.models.pipeline_job import PipelineJob
from app.models.raw_llm_response import RawLLMResponse
from app.models.user import User
from app.schemas.pipeline import (
    ExpandedQueryResponse,
    QueriesListResponse,
    RawResponseResponse,
    ResponsesListResponse,
)

from ._common import _add_sunset_headers

router = APIRouter()


@router.get("/jobs/{job_id}/queries", response_model=QueriesListResponse)
async def get_queries(
    job_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
    category_id: int | None = None,
):
    """Get expanded queries for a pipeline job."""
    _add_sunset_headers(response)
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
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
):
    """Get raw LLM responses for a query."""
    _add_sunset_headers(response)
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
