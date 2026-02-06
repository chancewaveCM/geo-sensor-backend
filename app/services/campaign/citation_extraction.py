"""Citation extraction service for LLM responses."""

import hashlib
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import RunResponse
from app.models.run_citation import RunCitation

logger = logging.getLogger(__name__)


class CitationExtractionService:
    """Extract citations from LLM responses and compute metrics."""

    async def extract_citations(
        self,
        response: RunResponse,
        target_brands: list[str],
        db: AsyncSession,
    ) -> list[RunCitation]:
        """
        Extract brand citations from a RunResponse's content.

        Uses simple text matching for MVP. Can be upgraded to LLM-based extraction later.
        """
        content = response.content
        citations: list[RunCitation] = []

        # Find all brand mentions in the response
        all_brands = self._find_brand_mentions(content, target_brands)

        for idx, mention in enumerate(all_brands, 1):
            # Extract context around the mention
            start = max(0, mention["start"] - 100)
            end = min(len(content), mention["end"] + 100)

            citation = RunCitation(
                run_response_id=response.id,
                cited_brand=mention["brand"],
                citation_span=content[mention["start"] : mention["end"]],
                context_before=(
                    content[start : mention["start"]] if start < mention["start"] else None
                ),
                context_after=content[mention["end"] : end] if mention["end"] < end else None,
                position_in_response=idx,
                is_target_brand=mention["brand"].lower() in [b.lower() for b in target_brands],
                confidence_score=mention.get("confidence", 0.8),
                extraction_method="text_match",
            )
            citations.append(citation)
            db.add(citation)

        # Update response metadata
        response.response_hash = hashlib.sha256(content.encode()).hexdigest()
        response.word_count = len(content.split())
        response.citation_count = len(citations)

        await db.flush()
        return citations

    def _find_brand_mentions(
        self, content: str, known_brands: list[str]
    ) -> list[dict[str, Any]]:
        """Find all brand mentions in text content."""
        mentions = []
        content_lower = content.lower()

        for brand in known_brands:
            brand_lower = brand.lower()
            start = 0
            while True:
                idx = content_lower.find(brand_lower, start)
                if idx == -1:
                    break
                mentions.append({
                    "brand": brand,
                    "start": idx,
                    "end": idx + len(brand),
                    "confidence": 0.85,
                })
                start = idx + len(brand)

        # Sort by position
        mentions.sort(key=lambda x: x["start"])
        return mentions
