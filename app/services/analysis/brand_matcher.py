"""
Brand Matcher
F5: Match brand names in AI responses with fuzzy matching
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Set
from difflib import SequenceMatcher
import re


class MatchType(Enum):
    """Type of brand match"""
    EXACT = "exact"           # Exact name match
    ALIAS = "alias"           # Known alias match
    FUZZY = "fuzzy"           # Fuzzy string match (>= threshold)
    KEYWORD = "keyword"       # Keyword-based match


@dataclass
class Brand:
    """Brand entity"""
    id: int
    name: str
    aliases: List[str]
    keywords: List[str]

    def all_names(self) -> Set[str]:
        """Get all searchable names (name + aliases)"""
        return {self.name.lower(), *(a.lower() for a in self.aliases)}


@dataclass
class BrandMatch:
    """A matched brand in text"""
    brand_id: int
    brand_name: str
    matched_text: str
    match_type: MatchType
    confidence: float  # 0.0 - 1.0
    position: int      # Character position in text
    context: str       # Surrounding text (±50 chars)

    def to_dict(self) -> dict:
        return {
            "brand_id": self.brand_id,
            "brand_name": self.brand_name,
            "matched_text": self.matched_text,
            "match_type": self.match_type.value,
            "confidence": round(self.confidence, 3),
            "position": self.position,
            "context": self.context,
        }


class BrandMatcher:
    """
    Match brand mentions in text using multiple strategies

    Matching strategies (in order):
    1. EXACT: Direct name match (case-insensitive)
    2. ALIAS: Known alias match
    3. FUZZY: String similarity (>= threshold)
    4. KEYWORD: Keyword presence + context
    """

    def __init__(
        self,
        brands: List[Brand],
        fuzzy_threshold: float = 0.85,
        keyword_threshold: float = 0.7,
    ):
        """
        Initialize brand matcher

        Args:
            brands: List of brands to match against
            fuzzy_threshold: Minimum similarity score for fuzzy match (0.0-1.0)
            keyword_threshold: Minimum confidence for keyword match (0.0-1.0)
        """
        self.brands = brands
        self.fuzzy_threshold = fuzzy_threshold
        self.keyword_threshold = keyword_threshold

        # Build lookup indices
        self._build_indices()

    def _build_indices(self):
        """Build fast lookup indices"""
        self.exact_index = {}
        self.alias_index = {}
        self.keyword_index = {}

        for brand in self.brands:
            # Exact name index
            self.exact_index[brand.name.lower()] = brand

            # Alias index
            for alias in brand.aliases:
                self.alias_index[alias.lower()] = brand

            # Keyword index
            for keyword in brand.keywords:
                if keyword.lower() not in self.keyword_index:
                    self.keyword_index[keyword.lower()] = []
                self.keyword_index[keyword.lower()].append(brand)

    def match(self, text: str) -> List[BrandMatch]:
        """
        Find all brand matches in text

        Args:
            text: Text to search for brand mentions

        Returns:
            List of BrandMatch objects, sorted by position
        """
        if not text or not text.strip():
            return []

        matches = []

        # 1. Exact and alias matches (word boundary-based)
        matches.extend(self._exact_match(text))

        # 2. Fuzzy matches (for missed brands)
        matched_brands = {m.brand_id for m in matches}
        matches.extend(self._fuzzy_match(text, matched_brands))

        # 3. Keyword matches (for indirect mentions)
        matches.extend(self._keyword_match(text, matched_brands))

        # Remove duplicates and sort by position
        matches = self._deduplicate(matches)
        matches.sort(key=lambda m: m.position)

        return matches

    def _exact_match(self, text: str) -> List[BrandMatch]:
        """Find exact name and alias matches"""
        matches = []
        text_lower = text.lower()

        # Try exact names
        for name, brand in self.exact_index.items():
            pattern = r'\b' + re.escape(name) + r'\b'
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                matches.append(BrandMatch(
                    brand_id=brand.id,
                    brand_name=brand.name,
                    matched_text=text[match.start():match.end()],
                    match_type=MatchType.EXACT,
                    confidence=1.0,
                    position=match.start(),
                    context=self._extract_context(text, match.start()),
                ))

        # Try aliases
        for alias, brand in self.alias_index.items():
            pattern = r'\b' + re.escape(alias) + r'\b'
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                matches.append(BrandMatch(
                    brand_id=brand.id,
                    brand_name=brand.name,
                    matched_text=text[match.start():match.end()],
                    match_type=MatchType.ALIAS,
                    confidence=0.95,
                    position=match.start(),
                    context=self._extract_context(text, match.start()),
                ))

        return matches

    def _fuzzy_match(self, text: str, exclude_brands: Set[int]) -> List[BrandMatch]:
        """Find fuzzy matches using string similarity"""
        matches = []
        words = re.findall(r'\b\w+\b', text.lower())

        for i, word in enumerate(words):
            if len(word) < 3:  # Skip very short words
                continue

            for brand in self.brands:
                if brand.id in exclude_brands:
                    continue

                # Check against brand name and aliases
                for name in brand.all_names():
                    similarity = SequenceMatcher(None, word, name).ratio()

                    if similarity >= self.fuzzy_threshold:
                        # Find position in original text
                        pos = text.lower().find(word)

                        matches.append(BrandMatch(
                            brand_id=brand.id,
                            brand_name=brand.name,
                            matched_text=word,
                            match_type=MatchType.FUZZY,
                            confidence=similarity,
                            position=pos,
                            context=self._extract_context(text, pos),
                        ))
                        exclude_brands.add(brand.id)
                        break

        return matches

    def _keyword_match(self, text: str, exclude_brands: Set[int]) -> List[BrandMatch]:
        """Find keyword-based matches"""
        matches = []
        text_lower = text.lower()

        for keyword, brands in self.keyword_index.items():
            if keyword not in text_lower:
                continue

            for brand in brands:
                if brand.id in exclude_brands:
                    continue

                # Check if brand is contextually relevant
                # (e.g., keyword + product category)
                pos = text_lower.find(keyword)
                context = self._extract_context(text, pos)

                # Simple heuristic: keyword presence = match
                # (can be enhanced with semantic similarity)
                matches.append(BrandMatch(
                    brand_id=brand.id,
                    brand_name=brand.name,
                    matched_text=keyword,
                    match_type=MatchType.KEYWORD,
                    confidence=self.keyword_threshold,
                    position=pos,
                    context=context,
                ))

        return matches

    def _extract_context(self, text: str, position: int, window: int = 50) -> str:
        """Extract surrounding context around match position"""
        start = max(0, position - window)
        end = min(len(text), position + window)
        context = text[start:end]

        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."

        return context

    def _deduplicate(self, matches: List[BrandMatch]) -> List[BrandMatch]:
        """Remove duplicate matches, keeping highest confidence"""
        seen = {}

        for match in matches:
            key = (match.brand_id, match.position)

            if key not in seen or match.confidence > seen[key].confidence:
                seen[key] = match

        return list(seen.values())

    def match_single_brand(self, text: str, brand_id: int) -> Optional[BrandMatch]:
        """
        Check if a specific brand is mentioned

        Args:
            text: Text to search
            brand_id: ID of brand to check

        Returns:
            First match found, or None
        """
        matches = self.match(text)
        for match in matches:
            if match.brand_id == brand_id:
                return match
        return None

    def get_brand_by_id(self, brand_id: int) -> Optional[Brand]:
        """Get brand by ID"""
        for brand in self.brands:
            if brand.id == brand_id:
                return brand
        return None
