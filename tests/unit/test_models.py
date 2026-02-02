import pytest
from app.models import User, Project, Brand, Query, Response, Citation, QueryStatus, LLMProvider, MatchType


def test_user_model_attributes():
    """Test User model has required attributes."""
    assert hasattr(User, "id")
    assert hasattr(User, "email")
    assert hasattr(User, "hashed_password")
    assert hasattr(User, "projects")


def test_project_model_attributes():
    """Test Project model has required attributes."""
    assert hasattr(Project, "id")
    assert hasattr(Project, "name")
    assert hasattr(Project, "owner_id")
    assert hasattr(Project, "brands")
    assert hasattr(Project, "queries")


def test_brand_model_attributes():
    """Test Brand model has required attributes."""
    assert hasattr(Brand, "id")
    assert hasattr(Brand, "name")
    assert hasattr(Brand, "aliases")
    assert hasattr(Brand, "keywords")
    assert hasattr(Brand, "project_id")


def test_query_model_attributes():
    """Test Query model has required attributes."""
    assert hasattr(Query, "id")
    assert hasattr(Query, "text")
    assert hasattr(Query, "status")
    assert hasattr(Query, "project_id")


def test_response_model_attributes():
    """Test Response model has required attributes."""
    assert hasattr(Response, "id")
    assert hasattr(Response, "content")
    assert hasattr(Response, "llm_provider")
    assert hasattr(Response, "llm_model")
    assert hasattr(Response, "sentiment_score")
    assert hasattr(Response, "geo_score")


def test_citation_model_attributes():
    """Test Citation model has required attributes."""
    assert hasattr(Citation, "id")
    assert hasattr(Citation, "matched_text")
    assert hasattr(Citation, "match_type")
    assert hasattr(Citation, "confidence")
    assert hasattr(Citation, "brand_id")
    assert hasattr(Citation, "response_id")


def test_query_status_enum():
    """Test QueryStatus enum values."""
    assert QueryStatus.PENDING == "pending"
    assert QueryStatus.PROCESSING == "processing"
    assert QueryStatus.COMPLETED == "completed"
    assert QueryStatus.FAILED == "failed"


def test_llm_provider_enum():
    """Test LLMProvider enum values."""
    assert LLMProvider.OPENAI == "openai"
    assert LLMProvider.GEMINI == "gemini"


def test_match_type_enum():
    """Test MatchType enum values."""
    assert MatchType.EXACT == "exact"
    assert MatchType.ALIAS == "alias"
    assert MatchType.FUZZY == "fuzzy"
    assert MatchType.KEYWORD == "keyword"
