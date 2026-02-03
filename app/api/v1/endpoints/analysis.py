"""Analysis orchestration endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.models.brand import Brand
from app.models.citation import Citation
from app.models.project import Project
from app.models.query import Query, QueryStatus
from app.models.response import LLMProvider, Response
from app.services.llm.constants import DEFAULT_MODELS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


# =============================================================================
# Request/Response Models
# =============================================================================

class AnalysisRequest(BaseModel):
    """Request to run analysis on a query."""
    query_id: int
    llm_providers: list[str] = Field(
        default=["gemini", "openai"],
        max_length=10,
        description="Which LLMs to query"
    )


class BrandCitationResult(BaseModel):
    """Citation result for a brand."""
    brand_id: int
    brand_name: str
    citation_count: int
    share_percentage: float
    matches: list[dict[str, Any]]


class AnalysisResponse(BaseModel):
    """Analysis response with all results."""
    query_id: int
    query_text: str
    status: str
    responses: list[dict[str, Any]]
    citation_shares: list[BrandCitationResult]
    total_citations: int


# =============================================================================
# Helper Functions
# =============================================================================

def _build_response_data(
    response: Response,
    sentiment_result=None,
    context_result=None,
    geo_result=None,
) -> dict[str, Any]:
    """Build standardized response data structure."""
    data: dict[str, Any] = {
        "id": response.id,
        "llm_provider": response.llm_provider.value,
        "llm_model": response.llm_model,
        "content": response.content,
    }

    # Use live results if provided, otherwise use stored values
    if sentiment_result:
        data["sentiment"] = {
            "score": sentiment_result.confidence,
            "label": sentiment_result.sentiment.value,
            "reasoning": sentiment_result.reasoning,
        }
    else:
        data["sentiment"] = {
            "score": response.sentiment_score,
            "label": response.sentiment_label,
        }

    if context_result:
        data["context_type"] = context_result.primary_context.value
    else:
        data["context_type"] = response.context_type

    if geo_result:
        data["geo_optimization"] = {
            "score": geo_result.total_score,
            "grade": geo_result.grade.value,
            "triggers": {t.trigger_type.value: t.detected for t in geo_result.triggers},
            "suggestions": geo_result.suggestions,
        }
    else:
        data["geo_optimization"] = {
            "score": response.geo_score,
            "grade": response.geo_grade,
            "triggers": response.geo_triggers,
        }

    return data


def _calculate_citation_shares_from_data(
    citations_data: list[dict[str, Any]],
) -> list[BrandCitationResult]:
    """Calculate citation shares from citation data list."""
    brand_counts: dict[int, dict] = {}

    for citation in citations_data:
        bid = citation["brand_id"]
        if bid not in brand_counts:
            brand_counts[bid] = {
                "brand_id": bid,
                "brand_name": citation["brand_name"],
                "count": 0,
                "matches": [],
            }
        brand_counts[bid]["count"] += 1
        brand_counts[bid]["matches"].append(citation)

    total = len(citations_data) or 1
    return [
        BrandCitationResult(
            brand_id=data["brand_id"],
            brand_name=data["brand_name"],
            citation_count=data["count"],
            share_percentage=round(data["count"] / total * 100, 2),
            matches=data["matches"],
        )
        for data in brand_counts.values()
    ]


async def _validate_and_load_query(
    db: DbSession,
    current_user: CurrentUser,
    query_id: int,
) -> tuple[Query, list[Brand]]:
    """Validate query ownership and load associated brands."""
    result = await db.execute(
        select(Query)
        .join(Project)
        .where(Query.id == query_id, Project.owner_id == current_user.id)
        .options(selectinload(Query.project))
    )
    query = result.scalar_one_or_none()
    if query is None:
        raise HTTPException(status_code=404, detail="Query not found")

    result = await db.execute(
        select(Brand).where(Brand.project_id == query.project_id)
    )
    brands = list(result.scalars().all())

    if not brands:
        raise HTTPException(
            status_code=400,
            detail="No brands configured for this project. Add brands first."
        )

    return query, brands


async def _handle_analysis_failure(
    db: DbSession,
    query_id: int,
) -> None:
    """Handle analysis failure - rollback and mark query as failed."""
    logger.exception(f"Analysis failed for query {query_id}")
    await db.rollback()

    result = await db.execute(select(Query).where(Query.id == query_id))
    query = result.scalar_one_or_none()
    if query:
        query.status = QueryStatus.FAILED
        await db.commit()


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/run", response_model=AnalysisResponse)
async def run_analysis(
    db: DbSession,
    current_user: CurrentUser,
    request: AnalysisRequest,
) -> AnalysisResponse:
    """
    Run full analysis pipeline on a query.

    This endpoint orchestrates:
    1. LLM queries (Gemini/OpenAI)
    2. Brand matching
    3. Sentiment analysis
    4. Context classification
    5. GEO optimization scoring
    6. Citation share calculation
    """
    # Validate and load data
    query, brands = await _validate_and_load_query(db, current_user, request.query_id)

    # Update query status
    query.status = QueryStatus.PROCESSING
    await db.commit()

    try:
        # Import analysis services (lazy import to avoid circular deps)
        from app.services.analysis.brand_matcher import Brand as BrandData
        from app.services.analysis.brand_matcher import BrandMatcher
        from app.services.analysis.citation_share import CitationShareCalculator
        from app.services.analysis.context_classifier import ContextClassifier
        from app.services.analysis.sentiment import SentimentAnalyzer
        from app.services.optimization.geo_analyzer import GEOOptimizationAnalyzer

        # Initialize analyzers
        brand_data_list = [
            BrandData(
                id=b.id,
                name=b.name,
                aliases=b.aliases or [],
                keywords=b.keywords or []
            )
            for b in brands
        ]
        matcher = BrandMatcher(brand_data_list)
        sentiment_analyzer = SentimentAnalyzer()
        context_classifier = ContextClassifier()
        geo_analyzer = GEOOptimizationAnalyzer()

        # Process each LLM provider
        responses_data = []
        all_matches = []
        all_citations_data: list[dict[str, Any]] = []

        # Mock content for development (LLM service will be integrated separately)
        mock_content = (
            f"Sample response for query: {query.text}. "
            "Samsung Galaxy is a great choice with innovative features. "
            "The iPhone also offers excellent performance. "
            "According to experts, both are top picks in 2024."
        )

        for provider_str in request.llm_providers:
            try:
                provider = LLMProvider(provider_str)
            except ValueError:
                continue  # Skip invalid providers

            # Create response record
            response = Response(
                content=mock_content,
                llm_provider=provider,
                llm_model=DEFAULT_MODELS.get(provider_str, "unknown"),
                query_id=query.id,
            )
            db.add(response)
            await db.flush()

            # Run brand matching
            matches = matcher.match(response.content)
            all_matches.extend(matches)

            # Save citations
            for match in matches:
                citation = Citation(
                    matched_text=match.matched_text,
                    match_type=match.match_type,  # Already correct enum type
                    confidence=match.confidence,
                    position_start=match.position,
                    position_end=match.position + len(match.matched_text),
                    brand_id=match.brand_id,
                    response_id=response.id,
                )
                db.add(citation)
                all_citations_data.append({
                    "brand_id": match.brand_id,
                    "brand_name": match.brand_name,
                    "matched_text": match.matched_text,
                    "match_type": match.match_type.value,
                    "confidence": match.confidence,
                })

            # Run analysis
            sentiment_result = sentiment_analyzer.analyze_sync(response.content)
            context_result = context_classifier.classify(response.content)
            geo_result = geo_analyzer.analyze(response.content)

            # Update response with analysis results
            response.sentiment_score = sentiment_result.confidence
            response.sentiment_label = sentiment_result.sentiment.value
            response.context_type = context_result.primary_context.value
            response.geo_score = geo_result.total_score
            response.geo_grade = geo_result.grade.value
            response.geo_triggers = {
                t.trigger_type.value: t.detected for t in geo_result.triggers
            }

            responses_data.append(_build_response_data(
                response, sentiment_result, context_result, geo_result
            ))

        # Calculate citation shares
        calculator = CitationShareCalculator()
        share_result = calculator.calculate(all_matches, query.id)

        citation_shares = [
            BrandCitationResult(
                brand_id=share.brand_id,
                brand_name=share.brand_name,
                citation_count=share.mention_count,
                share_percentage=share.share_percentage,
                matches=[c for c in all_citations_data if c["brand_id"] == share.brand_id],
            )
            for share in share_result.shares
        ]

        # Mark query as completed
        query.status = QueryStatus.COMPLETED
        await db.commit()

        return AnalysisResponse(
            query_id=query.id,
            query_text=query.text,
            status=query.status.value,
            responses=responses_data,
            citation_shares=citation_shares,
            total_citations=share_result.total_mentions,
        )

    except Exception:
        await _handle_analysis_failure(db, request.query_id)
        raise HTTPException(
            status_code=500,
            detail="Analysis failed. Please try again later."
        )


@router.get("/results/{query_id}", response_model=AnalysisResponse)
async def get_analysis_results(
    db: DbSession,
    current_user: CurrentUser,
    query_id: int,
) -> AnalysisResponse:
    """Get analysis results for a completed query."""
    # Get query with responses and citations
    result = await db.execute(
        select(Query)
        .join(Project)
        .where(Query.id == query_id, Project.owner_id == current_user.id)
        .options(
            selectinload(Query.responses).selectinload(Response.citations),
            selectinload(Query.project).selectinload(Project.brands),
        )
    )
    query = result.scalar_one_or_none()
    if query is None:
        raise HTTPException(status_code=404, detail="Query not found")

    if query.status != QueryStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Query analysis is not yet complete. Please wait and try again."
        )

    # Build response data
    responses_data = []
    all_citations: list[dict[str, Any]] = []

    for response in query.responses:
        responses_data.append(_build_response_data(response))

        for citation in response.citations:
            all_citations.append({
                "brand_id": citation.brand_id,
                "brand_name": next(
                    (b.name for b in query.project.brands if b.id == citation.brand_id),
                    "Unknown"
                ),
                "matched_text": citation.matched_text,
                "match_type": citation.match_type.value,
                "confidence": citation.confidence,
            })

    # Calculate citation shares
    citation_shares = _calculate_citation_shares_from_data(all_citations)

    return AnalysisResponse(
        query_id=query.id,
        query_text=query.text,
        status=query.status.value,
        responses=responses_data,
        citation_shares=citation_shares,
        total_citations=len(all_citations),
    )
