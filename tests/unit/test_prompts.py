"""Tests for LLM Prompt Templates"""

from app.services.llm.prompts import (
    CONTEXT_CLASSIFICATION_PROMPT,
    CONTEXT_SYSTEM_PROMPT,
    PROMPT_VERSIONS,
    SENTIMENT_ANALYSIS_PROMPT,
    SENTIMENT_SYSTEM_PROMPT,
)


class TestPromptStructure:
    def test_sentiment_prompt_has_json_format(self):
        """Sentiment prompt must specify JSON output format"""
        assert "json" in SENTIMENT_SYSTEM_PROMPT.lower()
        assert "sentiment" in SENTIMENT_SYSTEM_PROMPT.lower()
        assert "sentiment_score" in SENTIMENT_SYSTEM_PROMPT.lower()
        assert "confidence" in SENTIMENT_SYSTEM_PROMPT.lower()

    def test_sentiment_prompt_has_few_shot_examples(self):
        """Sentiment prompt must include few-shot learning examples"""
        assert "Example 1" in SENTIMENT_ANALYSIS_PROMPT
        assert "Example 2" in SENTIMENT_ANALYSIS_PROMPT
        assert "Example 3" in SENTIMENT_ANALYSIS_PROMPT
        assert "positive" in SENTIMENT_ANALYSIS_PROMPT
        assert "neutral" in SENTIMENT_ANALYSIS_PROMPT
        assert "negative" in SENTIMENT_ANALYSIS_PROMPT

    def test_context_prompt_has_unified_categories(self):
        """Context prompt must define all 5 unified categories"""
        categories = [
            "informational",
            "comparative",
            "recommendation",
            "tutorial",
            "opinion",
        ]

        for category in categories:
            assert category in CONTEXT_SYSTEM_PROMPT.lower()

    def test_context_prompt_has_few_shot_examples(self):
        """Context classification prompt must include examples for each category"""
        assert "Example 1" in CONTEXT_CLASSIFICATION_PROMPT
        assert "Example 2" in CONTEXT_CLASSIFICATION_PROMPT
        assert "Example 3" in CONTEXT_CLASSIFICATION_PROMPT
        assert "Example 4" in CONTEXT_CLASSIFICATION_PROMPT
        assert "Example 5" in CONTEXT_CLASSIFICATION_PROMPT

    def test_prompt_versions_defined(self):
        """Prompt versions must be tracked for reproducibility"""
        assert "sentiment_analysis" in PROMPT_VERSIONS
        assert "context_classification" in PROMPT_VERSIONS

        # Versions should be semantic version strings
        for version in PROMPT_VERSIONS.values():
            assert isinstance(version, str)
            assert len(version) > 0
            assert "." in version  # e.g., "1.0"
