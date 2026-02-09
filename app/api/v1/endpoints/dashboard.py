"""Dashboard aggregate API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import WorkspaceMemberDep, get_db
from app.models.expanded_query import ExpandedQuery
from app.models.pipeline_category import PipelineCategory
from app.models.pipeline_job import PipelineJob
from app.models.raw_llm_response import RawLLMResponse
from app.schemas.dashboard import (
    BrandRankingResponse,
    CitationShareResponse,
    CitationTrendItem,
    CitationTrendResponse,
    GeoScoreSummaryItem,
    GeoScoreSummaryResponse,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


async def _verify_job_workspace(
    db: AsyncSession,
    job_id: int,
    workspace_id: int,
) -> PipelineJob:
    """Verify pipeline job belongs to workspace and return it."""
    result = await db.execute(
        select(PipelineJob)
        .join(PipelineJob.company_profile)
        .where(
            PipelineJob.id == job_id,
            PipelineJob.company_profile.has(workspace_id=workspace_id),
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline job not found or access denied",
        )
    return job


@router.get(
    "/pipeline-jobs/{job_id}/citation-share",
    response_model=CitationShareResponse,
)
async def get_citation_share(
    job_id: int,
    member: WorkspaceMemberDep,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get citation share aggregation for a pipeline job.

    Calculates total citation share and breakdown by LLM provider.
    """
    # Verify access
    job = await _verify_job_workspace(db, job_id, member.workspace_id)

    # Count total responses (queries executed)
    total_queries_result = await db.execute(
        select(func.count(RawLLMResponse.id.distinct()))
        .join(ExpandedQuery, RawLLMResponse.query_id == ExpandedQuery.id)
        .join(PipelineCategory, ExpandedQuery.category_id == PipelineCategory.id)
        .where(
            PipelineCategory.query_set_id == job.query_set_id,
            RawLLMResponse.pipeline_job_id == job_id,
        )
    )
    total_queries = total_queries_result.scalar() or 0

    # For MVP, we don't have brand citations extracted yet
    # Return placeholder data structure
    # TODO: Integrate with brand matching service when available
    total_citations = 0
    by_provider = {provider: 0.0 for provider in job.llm_providers}

    return CitationShareResponse(
        total_citation_share=0.0,
        by_provider=by_provider,
        total_queries=total_queries,
        total_citations=total_citations,
    )


@router.get(
    "/pipeline-jobs/{job_id}/citation-trend",
    response_model=CitationTrendResponse,
)
async def get_citation_trend(
    job_id: int,
    member: WorkspaceMemberDep,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get time-series citation trend for a pipeline job.

    Returns citation share over time, useful for tracking changes.
    """
    # Verify access
    job = await _verify_job_workspace(db, job_id, member.workspace_id)

    # Get query set to find all jobs with same query set (time series)
    result = await db.execute(
        select(PipelineJob)
        .where(PipelineJob.query_set_id == job.query_set_id)
        .order_by(PipelineJob.started_at)
    )
    jobs = result.scalars().all()

    # For MVP, return placeholder time series
    # TODO: Integrate with brand matching service when available
    items = []
    for j in jobs:
        if j.started_at:
            items.append(
                CitationTrendItem(
                    date=j.started_at.date().isoformat(),
                    citation_share=0.0,
                    provider=None,
                )
            )

    return CitationTrendResponse(items=items)


@router.get(
    "/pipeline-jobs/{job_id}/brand-ranking",
    response_model=BrandRankingResponse,
)
async def get_brand_ranking(
    job_id: int,
    member: WorkspaceMemberDep,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get brand ranking list with citation metrics.

    Shows which brands are mentioned most frequently in LLM responses.
    """
    # Verify access
    _job = await _verify_job_workspace(db, job_id, member.workspace_id)

    # For MVP, return empty brand list
    # TODO: Integrate with brand matching service when available
    return BrandRankingResponse(
        brands=[],
        total_citations=0,
    )


@router.get(
    "/pipeline-jobs/{job_id}/geo-score-summary",
    response_model=GeoScoreSummaryResponse,
)
async def get_geo_score_summary(
    job_id: int,
    member: WorkspaceMemberDep,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get GEO 5-trigger summary for a pipeline job.

    Evaluates Generative Engine Optimization across 5 key triggers:
    1. Authoritative - Expert citations
    2. Factual - Data-backed claims
    3. Helpful - Direct answers
    4. Visual - Rich media
    5. Topical - Keyword relevance
    """
    # Verify access
    _job = await _verify_job_workspace(db, job_id, member.workspace_id)

    # For MVP, return placeholder GEO scores
    # TODO: Implement GEO analysis engine
    triggers = [
        GeoScoreSummaryItem(
            trigger="Authoritative",
            score=0.0,
            description="Expert citations and credibility signals",
        ),
        GeoScoreSummaryItem(
            trigger="Factual",
            score=0.0,
            description="Data-backed claims and statistics",
        ),
        GeoScoreSummaryItem(
            trigger="Helpful",
            score=0.0,
            description="Direct answers to user queries",
        ),
        GeoScoreSummaryItem(
            trigger="Visual",
            score=0.0,
            description="Rich media and visual elements",
        ),
        GeoScoreSummaryItem(
            trigger="Topical",
            score=0.0,
            description="Keyword relevance and semantic match",
        ),
    ]

    return GeoScoreSummaryResponse(
        overall_score=0.0,
        triggers=triggers,
    )
