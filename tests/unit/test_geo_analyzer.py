"""Tests for GEO Optimization Analyzer (F9)"""

import pytest
from app.services.optimization.geo_analyzer import (
    GEOOptimizationAnalyzer, Grade, TriggerType
)


@pytest.fixture
def analyzer():
    return GEOOptimizationAnalyzer()


class TestGEOOptimizationAnalyzer:
    def test_high_score_content(self, analyzer):
        content = '''
        Samsung Galaxy S24 is the flagship smartphone from Samsung.

        Key features:
        - 200MP camera
        - 5000mAh battery
        - AI features

        According to experts, "This is the best phone of 2024."
        The device scored 95% in user satisfaction surveys.

        In summary, the Galaxy S24 offers excellent value.
        '''

        result = analyzer.analyze(content, brand="Samsung")

        assert result.total_score >= 50
        assert result.grade in [Grade.A, Grade.B, Grade.C, Grade.D, Grade.F]

    def test_low_score_content(self, analyzer):
        content = "Samsung makes phones. They are phones."

        result = analyzer.analyze(content)

        assert result.total_score < 40
        assert result.grade in [Grade.D, Grade.F]

    def test_definition_detection(self, analyzer):
        content = "Samsung is a leading electronics manufacturer."
        result = analyzer.analyze(content, brand="Samsung")

        definition_trigger = next(
            t for t in result.triggers
            if t.trigger_type == TriggerType.CLEAR_DEFINITION
        )
        assert definition_trigger.detected

    def test_statistics_detection(self, analyzer):
        content = "The market share is 35% and growing. Top 3 in sales."
        result = analyzer.analyze(content)

        stats_trigger = next(
            t for t in result.triggers
            if t.trigger_type == TriggerType.STATISTICS
        )
        assert stats_trigger.detected
        assert stats_trigger.score > 0

    def test_structure_detection(self, analyzer):
        content = '''
        Features:
        - Fast processor
        - Great camera
        - Long battery
        '''
        result = analyzer.analyze(content)

        structure_trigger = next(
            t for t in result.triggers
            if t.trigger_type == TriggerType.STRUCTURED_INFO
        )
        assert structure_trigger.detected

    def test_suggestions_generated(self, analyzer):
        content = "Simple content without triggers."
        result = analyzer.analyze(content)

        assert len(result.suggestions) > 0

    def test_grade_calculation(self, analyzer):
        assert analyzer._calculate_grade(95) == Grade.A
        assert analyzer._calculate_grade(85) == Grade.B
        assert analyzer._calculate_grade(75) == Grade.C
        assert analyzer._calculate_grade(65) == Grade.D
        assert analyzer._calculate_grade(50) == Grade.F

    def test_result_to_dict(self, analyzer):
        result = analyzer.analyze("Test content")
        d = result.to_dict()

        assert "total_score" in d
        assert "grade" in d
        assert "triggers" in d
        assert "suggestions" in d
