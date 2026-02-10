"""Content Optimizer endpoints.

Provides text analysis, diagnosis, suggestions, and comparison
for optimizing content to improve AI citation likelihood.
"""

import json
import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.enums import LLMProvider
from app.models.user import User
from app.schemas.content_optimizer import (
    AnalysisHistoryResponse,
    AnalyzeTextRequest,
    AnalyzeUrlRequest,
    CitationScore,
    CompareRequest,
    CompareResult,
    DiagnoseRequest,
    DiagnosisItem,
    DiagnosisResult,
    SuggestionItem,
    SuggestRequest,
    SuggestResult,
)
from app.services.llm.factory import LLMFactory
from app.utils.ssrf_guard import validate_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content-optimizer", tags=["content-optimizer"])


def _get_api_key(provider: str) -> str:
    """Get API key for the given provider string."""
    if provider == "gemini":
        return settings.GEMINI_API_KEY
    elif provider == "openai":
        return settings.OPENAI_API_KEY
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid provider: {provider}",
    )


def _validate_provider(provider: str) -> None:
    """Validate LLM provider string."""
    valid = {p.value for p in LLMProvider}
    if provider not in valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider: {provider}. Valid: {valid}",
        )


async def _analyze_content(text: str, target_brand: str, provider: str) -> DiagnosisResult:
    """Analyze text content and return diagnosis."""
    _validate_provider(provider)
    llm = LLMFactory.create(LLMProvider(provider), _get_api_key(provider))

    prompt = f"""Analyze the following content for AI citation optimization potential.
Target brand: {target_brand}

Content:
{text[:10000]}

Return a JSON object with this exact structure:
{{
    "citation_score": {{
        "overall_score": <0-100>,
        "brand_mention_score": <0-100>,
        "authority_score": <0-100>,
        "structure_score": <0-100>,
        "freshness_score": <0-100>
    }},
    "findings": [
        {{
            "category": "<category>",
            "severity": "<critical|warning|info>",
            "title": "<short title>",
            "description": "<detailed description>",
            "recommendation": "<actionable recommendation>"
        }}
    ],
    "summary": "<2-3 sentence summary>"
}}

Return ONLY the JSON object, no markdown formatting."""

    try:
        response = await llm.generate(prompt, max_tokens=4096)
        # Try to parse the response as JSON
        content = response.content.strip()
        # Remove markdown code fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
        result = json.loads(content)
        return DiagnosisResult(
            citation_score=CitationScore(**result["citation_score"]),
            findings=[DiagnosisItem(**f) for f in result.get("findings", [])],
            summary=result.get("summary", "Analysis complete."),
        )
    except json.JSONDecodeError:
        # Return a basic result if LLM doesn't return valid JSON
        return DiagnosisResult(
            citation_score=CitationScore(
                overall_score=50.0,
                brand_mention_score=50.0,
                authority_score=50.0,
                structure_score=50.0,
                freshness_score=50.0,
            ),
            findings=[
                DiagnosisItem(
                    category="parsing",
                    severity="warning",
                    title="Analysis Incomplete",
                    description="The AI response could not be fully parsed.",
                    recommendation="Try again or use a different LLM provider.",
                )
            ],
            summary="Analysis partially complete. Please retry for full results.",
        )
    except Exception as e:
        logger.error(f"Content analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service error during analysis",
        )


@router.post("/analyze-text", response_model=DiagnosisResult)
async def analyze_text(
    request: AnalyzeTextRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Analyze text content for citation optimization potential."""
    return await _analyze_content(
        request.text, request.target_brand, request.llm_provider
    )


@router.post("/analyze-url", response_model=DiagnosisResult)
async def analyze_url(
    request: AnalyzeUrlRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Analyze a URL's content for citation optimization.

    Fetches the URL content (with SSRF protection) and analyzes it.
    """
    # Validate URL against SSRF
    validate_url(request.url)

    # Fetch URL content
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(request.url, follow_redirects=True)
            resp.raise_for_status()
            text = resp.text[:50000]  # Limit content size
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch URL: {e}",
        )

    return await _analyze_content(text, request.target_brand, request.llm_provider)


@router.post("/diagnose", response_model=DiagnosisResult)
async def diagnose_content(
    request: DiagnoseRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Detailed diagnosis of content with findings and recommendations."""
    return await _analyze_content(
        request.text, request.target_brand, request.llm_provider
    )


@router.post("/suggest", response_model=SuggestResult)
async def suggest_improvements(
    request: SuggestRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Generate optimization suggestions for content."""
    _validate_provider(request.llm_provider)
    llm = LLMFactory.create(
        LLMProvider(request.llm_provider),
        _get_api_key(request.llm_provider),
    )

    prompt = f"""Generate optimization suggestions to improve AI citation \
likelihood for this content.
Target brand: {request.target_brand}

Content:
{request.text[:10000]}

Return a JSON object with this exact structure:
{{
    "suggestions": [
        {{
            "category": "<category>",
            "priority": "<high|medium|low>",
            "title": "<short title>",
            "description": "<detailed description>",
            "example_before": "<original text snippet or null>",
            "example_after": "<improved text snippet or null>"
        }}
    ],
    "estimated_score_improvement": <0-100>,
    "summary": "<2-3 sentence summary>"
}}

Return ONLY the JSON object, no markdown formatting."""

    try:
        response = await llm.generate(prompt, max_tokens=4096)
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
        result = json.loads(content)
        return SuggestResult(
            suggestions=[SuggestionItem(**s) for s in result.get("suggestions", [])],
            estimated_score_improvement=result.get("estimated_score_improvement", 0),
            summary=result.get("summary", "Suggestions generated."),
        )
    except json.JSONDecodeError:
        return SuggestResult(
            suggestions=[],
            estimated_score_improvement=0,
            summary="Could not parse suggestions. Please retry.",
        )
    except Exception as e:
        logger.error(f"Suggestion generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service error during suggestion generation",
        )


@router.post("/compare", response_model=CompareResult)
async def compare_content(
    request: CompareRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Compare original vs optimized content scores."""
    _validate_provider(request.llm_provider)
    llm = LLMFactory.create(
        LLMProvider(request.llm_provider),
        _get_api_key(request.llm_provider),
    )

    prompt = f"""Compare these two versions of content for AI citation optimization.
Target brand: {request.target_brand}

ORIGINAL:
{request.original_text[:5000]}

OPTIMIZED:
{request.optimized_text[:5000]}

Return a JSON object with this exact structure:
{{
    "original_score": {{
        "overall_score": <0-100>,
        "brand_mention_score": <0-100>,
        "authority_score": <0-100>,
        "structure_score": <0-100>,
        "freshness_score": <0-100>
    }},
    "optimized_score": {{
        "overall_score": <0-100>,
        "brand_mention_score": <0-100>,
        "authority_score": <0-100>,
        "structure_score": <0-100>,
        "freshness_score": <0-100>
    }},
    "improvement": <percentage improvement>,
    "changes_summary": ["<change 1>", "<change 2>"]
}}

Return ONLY the JSON object, no markdown formatting."""

    try:
        response = await llm.generate(prompt, max_tokens=4096)
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
        result = json.loads(content)
        return CompareResult(
            original_score=CitationScore(**result["original_score"]),
            optimized_score=CitationScore(**result["optimized_score"]),
            improvement=result.get("improvement", 0),
            changes_summary=result.get("changes_summary", []),
        )
    except Exception as e:
        logger.error(f"Content comparison failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service error during comparison",
        )


@router.get("/history", response_model=AnalysisHistoryResponse)
async def get_analysis_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 20,
    offset: int = 0,
):
    """Get content analysis history.

    Note: History storage is a Phase 2 feature.
    Returns empty list for now - frontend can cache locally.
    """
    return AnalysisHistoryResponse(items=[], total=0)
