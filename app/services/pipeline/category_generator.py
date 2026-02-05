"""Category generation service for pipeline."""

import logging

from app.models.company_profile import CompanyProfile
from app.models.enums import PersonaType
from app.services.llm.base import BaseLLMService
from app.services.pipeline.prompt_loader import load_category_prompt
from app.services.pipeline.response_parser import parse_categories_response

logger = logging.getLogger(__name__)


class CategoryGeneratorService:
    """Generate query categories from company profile using LLM."""

    def __init__(self, llm_service: BaseLLMService):
        self.llm = llm_service

    async def generate(
        self,
        company_profile: CompanyProfile,
        count: int,
        persona_type: PersonaType,
    ) -> list[dict[str, str]]:
        """
        Generate categories for a persona type.

        Args:
            company_profile: Company to generate categories for
            count: Number of categories to generate
            persona_type: Consumer or Investor persona

        Returns:
            List of {"name": str, "description": str}
        """
        prompt = load_category_prompt(
            company_name=company_profile.name,
            industry=company_profile.industry,
            description=company_profile.description,
            target_audience=company_profile.target_audience,
            main_products=company_profile.main_products,
            competitors=company_profile.competitors,
            unique_value=company_profile.unique_value,
            persona_type=persona_type.value,
            category_count=count,
        )

        logger.info(
            f"Generating {count} categories for {company_profile.name} "
            f"({persona_type.value} persona)"
        )

        response = await self.llm.generate(
            prompt=prompt,
            temperature=0.7,
            max_tokens=2048,
        )

        return parse_categories_response(response.content, count)
