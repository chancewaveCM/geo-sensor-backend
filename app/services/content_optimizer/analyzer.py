"""Content Optimizer Analyzer Service.

Provides text analysis for citation optimization scoring.
"""

import json
import logging

from app.models.enums import LLMProvider
from app.services.llm.factory import LLMFactory

logger = logging.getLogger(__name__)


class ContentAnalyzer:
    """Analyzes text content for AI citation optimization potential."""

    def __init__(self, llm_provider: LLMProvider, api_key: str):
        self.llm = LLMFactory.create(llm_provider, api_key)
        self.provider = llm_provider

    async def compute_citation_score(
        self,
        text: str,
        target_brand: str,
    ) -> dict:
        """Compute citation optimization score for given text.

        Returns a dict with:
        - overall_score: float (0-100)
        - brand_mention_score: float (0-100)
        - authority_score: float (0-100)
        - structure_score: float (0-100)
        - freshness_score: float (0-100)
        """
        prompt = self._build_score_prompt(text, target_brand)
        try:
            response = await self.llm.generate(prompt, max_tokens=2048)
            return self._parse_score_response(response.content)
        except Exception as e:
            logger.error(f"Citation score computation failed: {e}")
            return self._default_scores()

    async def diagnose(
        self,
        text: str,
        target_brand: str,
    ) -> dict:
        """Run full diagnosis on content.

        Returns a dict with:
        - citation_score: dict
        - findings: list[dict]
        - summary: str
        """
        prompt_path = "app/prompts/content_optimizer/diagnose.txt"
        try:
            with open(prompt_path, encoding="utf-8") as f:
                prompt_template = f.read()
        except FileNotFoundError:
            prompt_template = self._fallback_diagnose_prompt()

        prompt = prompt_template.replace("{{TARGET_BRAND}}", target_brand)
        prompt = prompt.replace("{{CONTENT}}", text[:10000])

        try:
            response = await self.llm.generate(prompt, max_tokens=4096)
            return self._parse_json_response(response.content)
        except Exception as e:
            logger.error(f"Diagnosis failed: {e}")
            return {
                "citation_score": self._default_scores(),
                "findings": [],
                "summary": f"Diagnosis failed: {e}",
            }

    async def suggest(
        self,
        text: str,
        target_brand: str,
    ) -> dict:
        """Generate optimization suggestions.

        Returns a dict with:
        - suggestions: list[dict]
        - estimated_score_improvement: float
        - summary: str
        """
        prompt_path = "app/prompts/content_optimizer/suggest.txt"
        try:
            with open(prompt_path, encoding="utf-8") as f:
                prompt_template = f.read()
        except FileNotFoundError:
            prompt_template = self._fallback_suggest_prompt()

        prompt = prompt_template.replace("{{TARGET_BRAND}}", target_brand)
        prompt = prompt.replace("{{CONTENT}}", text[:10000])

        try:
            response = await self.llm.generate(prompt, max_tokens=4096)
            return self._parse_json_response(response.content)
        except Exception as e:
            logger.error(f"Suggestion generation failed: {e}")
            return {
                "suggestions": [],
                "estimated_score_improvement": 0,
                "summary": f"Suggestion generation failed: {e}",
            }

    def _build_score_prompt(self, text: str, target_brand: str) -> str:
        return f"""Score this content for AI citation optimization (0-100 each).
Target brand: {target_brand}

Content (first 5000 chars):
{text[:5000]}

Return ONLY a JSON object:
{{
    "overall_score": <0-100>,
    "brand_mention_score": <0-100>,
    "authority_score": <0-100>,
    "structure_score": <0-100>,
    "freshness_score": <0-100>
}}"""

    def _parse_score_response(self, content: str) -> dict:
        """Parse LLM response into score dict."""
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
        try:
            data = json.loads(content)
            return {
                "overall_score": float(data.get("overall_score", 50)),
                "brand_mention_score": float(data.get("brand_mention_score", 50)),
                "authority_score": float(data.get("authority_score", 50)),
                "structure_score": float(data.get("structure_score", 50)),
                "freshness_score": float(data.get("freshness_score", 50)),
            }
        except (json.JSONDecodeError, TypeError, ValueError):
            return self._default_scores()

    def _parse_json_response(self, content: str) -> dict:
        """Parse LLM response as JSON with fallback."""
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _default_scores() -> dict:
        return {
            "overall_score": 50.0,
            "brand_mention_score": 50.0,
            "authority_score": 50.0,
            "structure_score": 50.0,
            "freshness_score": 50.0,
        }

    @staticmethod
    def _fallback_diagnose_prompt() -> str:
        return """Analyze this content for AI citation optimization.
Target brand: {{TARGET_BRAND}}

Content:
{{CONTENT}}

Return a JSON object:
{
    "citation_score": {
        "overall_score": <0-100>,
        "brand_mention_score": <0-100>,
        "authority_score": <0-100>,
        "structure_score": <0-100>,
        "freshness_score": <0-100>
    },
    "findings": [
        {
            "category": "<category>",
            "severity": "<critical|warning|info>",
            "title": "<title>",
            "description": "<description>",
            "recommendation": "<recommendation>"
        }
    ],
    "summary": "<summary>"
}

Return ONLY the JSON."""

    @staticmethod
    def _fallback_suggest_prompt() -> str:
        return """Generate optimization suggestions for AI citation improvement.
Target brand: {{TARGET_BRAND}}

Content:
{{CONTENT}}

Return a JSON object:
{
    "suggestions": [
        {
            "category": "<category>",
            "priority": "<high|medium|low>",
            "title": "<title>",
            "description": "<description>",
            "example_before": "<before or null>",
            "example_after": "<after or null>"
        }
    ],
    "estimated_score_improvement": <0-100>,
    "summary": "<summary>"
}

Return ONLY the JSON."""
