"""Generated Query endpoints."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.models.company_profile import CompanyProfile
from app.models.enums import LLMProvider
from app.models.generated_query import GeneratedQuery, GeneratedQueryStatus, QueryCategory
from app.schemas.generated_query import (
    BulkUpdateRequest,
    GeneratedQueryResponse,
    GeneratedQueryUpdate,
    GenerateQueriesRequest,
)
from app.services.llm.factory import LLMFactory

router = APIRouter(prefix="/generated-queries", tags=["generated-queries"])


def parse_queries_from_response(response_text: str) -> list[dict]:
    """Parse 30 queries from LLM response."""
    lines = [line.strip() for line in response_text.strip().split('\n') if line.strip()]
    queries = []

    for i, line in enumerate(lines[:30], start=1):
        # 번호 제거 (예: "1. 질문" -> "질문")
        text = line.lstrip('0123456789.').strip()
        if not text:
            continue

        # 카테고리 분류
        if i <= 10:
            category = QueryCategory.INTRODUCTORY
        elif i <= 20:
            category = QueryCategory.COMPARATIVE
        else:
            category = QueryCategory.CRITICAL

        queries.append({
            "text": text,
            "order_index": i,
            "category": category,
        })

    return queries


@router.post(
    "/generate",
    response_model=list[GeneratedQueryResponse],
    status_code=status.HTTP_201_CREATED,
)
async def generate_queries(
    data: GenerateQueriesRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> list[GeneratedQuery]:
    """Generate 30 queries using Gemini for a company profile."""
    # 회사 프로필 조회
    result = await db.execute(
        select(CompanyProfile).where(
            CompanyProfile.id == data.company_profile_id,
            CompanyProfile.owner_id == current_user.id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found",
        )

    # 기업 정보 문자열 생성
    company_info = f"""
기업명: {profile.name}
산업: {profile.industry}
설명: {profile.description}
타겟 고객: {profile.target_audience or 'N/A'}
주요 제품/서비스: {profile.main_products or 'N/A'}
경쟁사: {profile.competitors or 'N/A'}
차별화 포인트: {profile.unique_value or 'N/A'}
웹사이트: {profile.website_url or 'N/A'}
"""

    # 프롬프트 로드 및 변수 대체
    prompt_path = "prompt/01.analysis/01.gen_target_query.txt"
    with open(prompt_path, encoding="utf-8") as f:
        prompt_template = f.read()

    prompt = prompt_template.replace(
        "[기업 정보] (여기에 분석할 기업 정보를 입력하세요)",
        f"[기업 정보]\n{company_info}",
    )

    # Gemini API 호출
    llm = LLMFactory.create(LLMProvider.GEMINI, settings.GEMINI_API_KEY)
    try:
        response = await llm.generate(prompt)
        response_text = response.content  # LLMResponse 객체에서 content 추출
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM service error: {str(e)}"
        )

    # 응답 파싱
    parsed_queries = parse_queries_from_response(response_text)

    if len(parsed_queries) < 10:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate sufficient queries from AI"
        )

    # 기존 쿼리 삭제 (재생성 시)
    await db.execute(
        select(GeneratedQuery).where(GeneratedQuery.company_profile_id == profile.id)
    )
    existing = (await db.execute(
        select(GeneratedQuery).where(GeneratedQuery.company_profile_id == profile.id)
    )).scalars().all()
    for q in existing:
        await db.delete(q)

    # 새 쿼리 저장
    queries = []
    for q_data in parsed_queries:
        query = GeneratedQuery(
            **q_data,
            company_profile_id=profile.id,
            original_text=q_data["text"],
        )
        db.add(query)
        queries.append(query)

    await db.commit()
    for q in queries:
        await db.refresh(q)

    return queries


@router.get("/", response_model=list[GeneratedQueryResponse])
async def list_generated_queries(
    company_profile_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[GeneratedQuery]:
    """List generated queries for a company profile."""
    # 권한 확인
    profile_result = await db.execute(
        select(CompanyProfile).where(
            CompanyProfile.id == company_profile_id,
            CompanyProfile.owner_id == current_user.id,
        )
    )
    if not profile_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found",
        )

    result = await db.execute(
        select(GeneratedQuery)
        .where(GeneratedQuery.company_profile_id == company_profile_id)
        .order_by(GeneratedQuery.order_index)
    )
    return list(result.scalars().all())


@router.put("/{query_id}", response_model=GeneratedQueryResponse)
async def update_generated_query(
    query_id: int,
    data: GeneratedQueryUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> GeneratedQuery:
    """Update a generated query (edit text, toggle selection)."""
    result = await db.execute(
        select(GeneratedQuery)
        .join(CompanyProfile)
        .where(GeneratedQuery.id == query_id, CompanyProfile.owner_id == current_user.id)
    )
    query = result.scalar_one_or_none()
    if not query:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Query not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "text" and value != query.text:
            query.status = GeneratedQueryStatus.EDITED
        setattr(query, field, value)

    await db.commit()
    await db.refresh(query)
    return query


@router.post("/bulk-update", response_model=list[GeneratedQueryResponse])
async def bulk_update_queries(
    data: BulkUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> list[GeneratedQuery]:
    """Bulk update queries (select/exclude multiple)."""
    result = await db.execute(
        select(GeneratedQuery)
        .join(CompanyProfile)
        .where(GeneratedQuery.id.in_(data.query_ids), CompanyProfile.owner_id == current_user.id)
    )
    queries = list(result.scalars().all())

    for query in queries:
        if data.is_selected is not None:
            query.is_selected = data.is_selected
        if data.status is not None:
            query.status = data.status

    await db.commit()
    for q in queries:
        await db.refresh(q)

    return queries
