"""Query expansion service for pipeline."""

import logging

from app.models.company_profile import CompanyProfile
from app.models.pipeline_category import PipelineCategory
from app.services.llm.base import BaseLLMService
from app.services.pipeline.prompt_loader import load_query_expansion_prompt
from app.services.pipeline.response_parser import parse_queries_response

logger = logging.getLogger(__name__)


class QueryExpanderService:
    """Expand categories into specific queries using LLM."""

    def __init__(self, llm_service: BaseLLMService):
        self.llm = llm_service

    async def expand(
        self,
        company_profile: CompanyProfile,
        category: PipelineCategory,
        query_count: int,
    ) -> list[str]:
        """
        Expand a category into multiple queries.

        Args:
            company_profile: Company context
            category: Category to expand
            query_count: Number of queries to generate

        Returns:
            List of query strings
        """
        prompt = load_query_expansion_prompt(
            company_name=company_profile.name,
            industry=company_profile.industry,
            description=company_profile.description,
            category_name=category.name,
            category_description=category.description or "",
            persona_type=category.persona_type.value,
            query_count=query_count,
        )

        logger.info(f"Expanding category '{category.name}' into {query_count} queries")

        response = await self.llm.generate(
            prompt=prompt,
            temperature=0.8,  # Slightly higher for variety
            max_tokens=2048,
        )

        return parse_queries_response(response.content, query_count)
