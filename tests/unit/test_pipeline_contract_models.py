"""Contract guard tests for pipeline frontend-backend schema sync."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.api.v1.endpoints import pipeline
from app.main import app


def test_company_profile_pipeline_stats_contract_fields():
    payload = {
        "company_profile_id": 1,
        "company_name": "ACME",
        "total_query_sets": 3,
        "total_jobs": 20,
        "completed_jobs": 18,
        "failed_jobs": 2,
        "success_rate_30d": 90.0,
        "last_run_status": "completed",
        "last_run_at": datetime.now(tz=UTC),
        "avg_processing_time_seconds": 32.5,
        "data_freshness_hours": 4.2,
        "health_grade": "green",
    }

    model = pipeline.CompanyProfilePipelineStats.model_validate(payload)
    assert model.total_query_sets == 3
    assert model.success_rate_30d == 90.0
    assert model.health_grade == "green"


def test_queryset_detail_contract_requires_total_jobs_and_detail_last_job_shape():
    payload = {
        "id": 10,
        "name": "Daily",
        "description": None,
        "category_count": 5,
        "queries_per_category": 8,
        "company_profile_id": 1,
        "created_at": datetime.now(tz=UTC),
        "categories": [],
        "last_job": {
            "id": 100,
            "status": "completed",
            "llm_providers": ["gemini"],
            "total_queries": 40,
            "completed_queries": 40,
            "failed_queries": 0,
            "started_at": datetime.now(tz=UTC),
            "completed_at": datetime.now(tz=UTC),
        },
        "total_jobs": 7,
        "total_responses": 120,
    }

    model = pipeline.QuerySetDetailResponse.model_validate(payload)
    assert model.total_jobs == 7
    assert model.last_job is not None
    assert model.last_job.total_queries == 40


def test_schedule_config_contract_requires_company_fields():
    payload = {
        "id": 1,
        "query_set_id": 3,
        "query_set_name": "QS",
        "company_profile_id": 99,
        "company_name": "ACME",
        "interval_minutes": 60,
        "is_active": True,
        "last_run_at": None,
        "next_run_at": None,
        "llm_providers": ["gemini", "openai"],
        "created_at": datetime.now(tz=UTC),
    }
    model = pipeline.ScheduleConfigResponse.model_validate(payload)
    assert model.company_profile_id == 99
    assert model.company_name == "ACME"

    invalid = payload.copy()
    invalid.pop("company_name")
    with pytest.raises(ValidationError):
        pipeline.ScheduleConfigResponse.model_validate(invalid)


def test_list_schedules_exposes_expected_query_filters():
    route = next(
        r
        for r in app.routes
        if getattr(r, "path", None) == "/api/v1/pipeline/schedules"
        and "GET" in getattr(r, "methods", set())
    )
    query_param_names = {param.name for param in route.dependant.query_params}

    assert "query_set_id" in query_param_names
    assert "company_profile_id" in query_param_names
