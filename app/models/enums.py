# app/models/enums.py

import enum


class LLMProvider(str, enum.Enum):
    """Canonical LLM provider enum - use throughout codebase."""
    OPENAI = "openai"
    GEMINI = "gemini"


class PersonaType(str, enum.Enum):
    """Persona types for query generation."""
    CONSUMER = "consumer"
    INVESTOR = "investor"


class PipelineStatus(str, enum.Enum):
    """Pipeline job execution status."""
    PENDING = "pending"
    GENERATING_CATEGORIES = "generating_categories"
    EXPANDING_QUERIES = "expanding_queries"
    EXECUTING_QUERIES = "executing_queries"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExpandedQueryStatus(str, enum.Enum):
    """Status of an expanded query."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
