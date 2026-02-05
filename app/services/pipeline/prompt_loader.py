"""Prompt loading and formatting utilities for pipeline."""

from pathlib import Path
from string import Template

# Prompt directory relative to backend root
PROMPT_DIR = Path(__file__).parent.parent.parent.parent / "prompt" / "02.pipeline"

PERSONA_DESCRIPTIONS = {
    "consumer": (
        "A potential customer evaluating whether to purchase products/services "
        "from this company. Focused on quality, price, reliability, user experience, "
        "and alternatives."
    ),
    "investor": (
        "A potential investor or analyst evaluating the company's market position, "
        "growth potential, financial health, competitive advantages, and risks."
    ),
}


def load_category_prompt(
    company_name: str,
    industry: str,
    description: str,
    target_audience: str,
    main_products: str,
    competitors: str,
    unique_value: str,
    persona_type: str,
    category_count: int,
) -> str:
    """Load and format category generation prompt."""
    template_path = PROMPT_DIR / "01.gen_categories.txt"
    template = Template(template_path.read_text(encoding="utf-8"))

    return template.safe_substitute(
        company_name=company_name,
        industry=industry,
        description=description,
        target_audience=target_audience or "General consumers",
        main_products=main_products or "Various products/services",
        competitors=competitors or "Industry competitors",
        unique_value=unique_value or "Quality and service",
        persona_type=persona_type,
        persona_description=PERSONA_DESCRIPTIONS[persona_type],
        category_count=category_count,
    )


def load_query_expansion_prompt(
    company_name: str,
    industry: str,
    description: str,
    category_name: str,
    category_description: str,
    persona_type: str,
    query_count: int,
) -> str:
    """Load and format query expansion prompt."""
    template_path = PROMPT_DIR / "02.expand_queries.txt"
    template = Template(template_path.read_text(encoding="utf-8"))

    return template.safe_substitute(
        company_name=company_name,
        industry=industry,
        description=description,
        category_name=category_name,
        category_description=category_description,
        persona_type=persona_type,
        query_count=query_count,
    )
