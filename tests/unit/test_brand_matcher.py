"""Tests for Brand Matching Engine (F5)"""

import pytest

from app.services.analysis.brand_matcher import Brand, BrandMatcher, MatchType


@pytest.fixture
def sample_brands():
    return [
        Brand(id=1, name="Samsung", aliases=["삼성"], keywords=["galaxy"]),
        Brand(id=2, name="Apple", aliases=["애플"], keywords=["iphone"]),
    ]


@pytest.fixture
def matcher(sample_brands):
    return BrandMatcher(brands=sample_brands, fuzzy_threshold=0.8)


class TestBrandMatcher:
    def test_exact_match(self, matcher):
        text = "Samsung Galaxy S24 is great"
        matches = matcher.match(text)

        samsung_matches = [m for m in matches if m.brand_name == "Samsung" and m.match_type == MatchType.EXACT]
        assert len(samsung_matches) >= 1
        assert samsung_matches[0].confidence == 1.0

    def test_alias_match_korean(self, matcher):
        text = "삼성 갤럭시가 좋습니다"
        matches = matcher.match(text)

        alias_matches = [m for m in matches if m.match_type == MatchType.ALIAS]
        assert len(alias_matches) >= 1
        assert alias_matches[0].brand_name == "Samsung"

    def test_keyword_match(self, matcher):
        text = "The new iPhone 15 Pro is amazing"
        matches = matcher.match(text)

        keyword_matches = [m for m in matches if m.match_type == MatchType.KEYWORD]
        assert len(keyword_matches) >= 1
        assert any(m.brand_name == "Apple" for m in keyword_matches)

    def test_multiple_brands(self, matcher):
        text = "Samsung vs Apple: Which is better?"
        matches = matcher.match(text)

        brand_names = {m.brand_name for m in matches}
        assert "Samsung" in brand_names
        assert "Apple" in brand_names

    def test_position_tracking(self, matcher):
        text = "I love Samsung phones"
        matches = matcher.match(text)

        assert len(matches) >= 1
        samsung_match = next(m for m in matches if m.brand_name == "Samsung")
        assert samsung_match.position == 7

    def test_case_insensitive(self, matcher):
        text = "SAMSUNG and samsung both work"
        matches = matcher.match(text)

        samsung_matches = [m for m in matches if m.brand_name == "Samsung"]
        assert len(samsung_matches) >= 2

    def test_empty_text(self, matcher):
        matches = matcher.match("")
        assert len(matches) == 0

    def test_no_matches(self, matcher):
        text = "This text has no brand mentions"
        matches = matcher.match(text)
        assert len(matches) == 0
