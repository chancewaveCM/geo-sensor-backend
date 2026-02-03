"""
Citation Share Calculator
F8: Calculate brand citation share percentage
"""

from collections import defaultdict
from dataclasses import dataclass, field

from .brand_matcher import BrandMatch, MatchType


@dataclass
class CitationShare:
    """Citation share for a single brand"""
    brand_id: int
    brand_name: str
    mention_count: int
    share_percentage: float  # 0.0 - 100.0
    match_types: dict[str, int] = field(default_factory=dict)
    avg_confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "brand_id": self.brand_id,
            "brand_name": self.brand_name,
            "mention_count": self.mention_count,
            "share_percentage": round(self.share_percentage, 2),
            "match_types": self.match_types,
            "avg_confidence": round(self.avg_confidence, 3),
        }


@dataclass
class CitationShareResult:
    """Complete citation share analysis result"""
    shares: list[CitationShare]
    total_mentions: int
    unique_brands: int
    query_id: int | None = None

    def to_dict(self) -> dict:
        return {
            "shares": [s.to_dict() for s in self.shares],
            "total_mentions": self.total_mentions,
            "unique_brands": self.unique_brands,
            "query_id": self.query_id,
        }


class CitationShareCalculator:
    """
    Calculate brand citation share from matches

    Citation Share = (Brand Mentions / Total Mentions) * 100

    Provides:
    - Per-brand share percentages
    - Match type breakdown
    - Average confidence scores
    """

    def calculate(
        self,
        matches: list[BrandMatch],
        query_id: int | None = None,
    ) -> CitationShareResult:
        """
        Calculate citation share from brand matches

        Args:
            matches: List of brand matches from BrandMatcher
            query_id: Optional query ID for tracking

        Returns:
            CitationShareResult with share percentages for each brand
        """
        if not matches:
            return CitationShareResult(
                shares=[],
                total_mentions=0,
                unique_brands=0,
                query_id=query_id,
            )

        # Aggregate by brand
        brand_data: dict[int, dict] = defaultdict(lambda: {
            "brand_name": "",
            "count": 0,
            "match_types": defaultdict(int),
            "confidences": [],
        })

        for match in matches:
            data = brand_data[match.brand_id]
            data["brand_name"] = match.brand_name
            data["count"] += 1
            data["match_types"][match.match_type.value] += 1
            data["confidences"].append(match.confidence)

        # Calculate shares
        total_mentions = len(matches)
        shares: list[CitationShare] = []

        for brand_id, data in brand_data.items():
            avg_confidence = sum(data["confidences"]) / len(data["confidences"])
            share_pct = (data["count"] / total_mentions) * 100

            shares.append(CitationShare(
                brand_id=brand_id,
                brand_name=data["brand_name"],
                mention_count=data["count"],
                share_percentage=share_pct,
                match_types=dict(data["match_types"]),
                avg_confidence=avg_confidence,
            ))

        # Sort by share percentage (descending)
        shares.sort(key=lambda s: s.share_percentage, reverse=True)

        return CitationShareResult(
            shares=shares,
            total_mentions=total_mentions,
            unique_brands=len(shares),
            query_id=query_id,
        )

    def calculate_aggregated(
        self,
        matches_by_query: dict[int, list[BrandMatch]],
    ) -> CitationShareResult:
        """
        Calculate aggregated citation share across multiple queries

        Args:
            matches_by_query: Dict mapping query_id to list of matches

        Returns:
            Aggregated CitationShareResult
        """
        all_matches = []
        for matches in matches_by_query.values():
            all_matches.extend(matches)

        return self.calculate(all_matches)

    def calculate_weighted(
        self,
        matches: list[BrandMatch],
        query_id: int | None = None,
    ) -> CitationShareResult:
        """
        Calculate weighted citation share based on confidence and match type

        Weights:
        - EXACT: 1.0
        - ALIAS: 0.95
        - FUZZY: confidence score
        - KEYWORD: 0.7
        """
        if not matches:
            return CitationShareResult(
                shares=[],
                total_mentions=0,
                unique_brands=0,
                query_id=query_id,
            )

        # Weight mapping
        type_weights = {
            MatchType.EXACT: 1.0,
            MatchType.ALIAS: 0.95,
            MatchType.FUZZY: None,  # Use confidence
            MatchType.KEYWORD: 0.7,
        }

        # Calculate weighted scores
        brand_weights: dict[int, dict] = defaultdict(lambda: {
            "brand_name": "",
            "weight": 0.0,
            "count": 0,
            "match_types": defaultdict(int),
            "confidences": [],
        })

        total_weight = 0.0

        for match in matches:
            weight = type_weights.get(match.match_type)
            if weight is None:
                weight = match.confidence

            data = brand_weights[match.brand_id]
            data["brand_name"] = match.brand_name
            data["weight"] += weight
            data["count"] += 1
            data["match_types"][match.match_type.value] += 1
            data["confidences"].append(match.confidence)

            total_weight += weight

        # Calculate shares
        shares: list[CitationShare] = []

        for brand_id, data in brand_weights.items():
            avg_confidence = sum(data["confidences"]) / len(data["confidences"])
            share_pct = (data["weight"] / total_weight) * 100 if total_weight > 0 else 0

            shares.append(CitationShare(
                brand_id=brand_id,
                brand_name=data["brand_name"],
                mention_count=data["count"],
                share_percentage=share_pct,
                match_types=dict(data["match_types"]),
                avg_confidence=avg_confidence,
            ))

        shares.sort(key=lambda s: s.share_percentage, reverse=True)

        return CitationShareResult(
            shares=shares,
            total_mentions=len(matches),
            unique_brands=len(shares),
            query_id=query_id,
        )
