"""Tests for Citation Share Calculator (F8)"""

import pytest
from app.services.analysis.citation_share import CitationShareCalculator
from app.services.analysis.brand_matcher import BrandMatch, MatchType


@pytest.fixture
def calculator():
    return CitationShareCalculator()


@pytest.fixture
def sample_matches():
    return [
        BrandMatch(brand_id=1, brand_name="Samsung", matched_text="Samsung",
                   match_type=MatchType.EXACT, position=0, confidence=1.0, context="Samsung Galaxy"),
        BrandMatch(brand_id=1, brand_name="Samsung", matched_text="Samsung",
                   match_type=MatchType.EXACT, position=50, confidence=1.0, context="Samsung phones"),
        BrandMatch(brand_id=2, brand_name="Apple", matched_text="Apple",
                   match_type=MatchType.EXACT, position=100, confidence=1.0, context="Apple iPhone"),
    ]


class TestCitationShareCalculator:
    def test_calculate_share(self, calculator, sample_matches):
        result = calculator.calculate(sample_matches)

        assert result.total_mentions == 3
        assert result.unique_brands == 2

        samsung_share = next(s for s in result.shares if s.brand_name == "Samsung")
        apple_share = next(s for s in result.shares if s.brand_name == "Apple")

        assert samsung_share.mention_count == 2
        assert abs(samsung_share.share_percentage - 66.67) < 1
        assert apple_share.mention_count == 1
        assert abs(apple_share.share_percentage - 33.33) < 1

    def test_empty_matches(self, calculator):
        result = calculator.calculate([])

        assert result.total_mentions == 0
        assert result.unique_brands == 0
        assert len(result.shares) == 0

    def test_single_brand(self, calculator):
        matches = [
            BrandMatch(brand_id=1, brand_name="Samsung", matched_text="Samsung",
                       match_type=MatchType.EXACT, position=0, confidence=1.0, context="Samsung Galaxy"),
        ]
        result = calculator.calculate(matches)

        assert result.total_mentions == 1
        assert result.shares[0].share_percentage == 100.0

    def test_shares_sum_to_100(self, calculator, sample_matches):
        result = calculator.calculate(sample_matches)

        total_percentage = sum(s.share_percentage for s in result.shares)
        assert abs(total_percentage - 100.0) < 0.01

    def test_match_type_breakdown(self, calculator, sample_matches):
        result = calculator.calculate(sample_matches)

        samsung_share = next(s for s in result.shares if s.brand_name == "Samsung")
        assert "exact" in samsung_share.match_types
        assert samsung_share.match_types["exact"] == 2

    def test_result_to_dict(self, calculator, sample_matches):
        result = calculator.calculate(sample_matches)
        d = result.to_dict()

        assert "shares" in d
        assert "total_mentions" in d
        assert "unique_brands" in d
