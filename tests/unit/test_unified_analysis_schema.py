import pytest
from pydantic import ValidationError

from app.schemas.unified_analysis import RerunQueryRequest, StartAnalysisRequest


def test_start_analysis_rejects_duplicate_llm_providers() -> None:
    with pytest.raises(ValidationError):
        StartAnalysisRequest(
            company_profile_id=1,
            mode="quick",
            llm_providers=["gemini", "gemini"],
        )


def test_rerun_query_rejects_duplicate_llm_providers() -> None:
    with pytest.raises(ValidationError):
        RerunQueryRequest(llm_providers=["openai", "openai"])


def test_start_analysis_accepts_unique_llm_providers() -> None:
    request = StartAnalysisRequest(
        company_profile_id=1,
        mode="advanced",
        llm_providers=["gemini", "openai"],
    )
    assert request.llm_providers == ["gemini", "openai"]
