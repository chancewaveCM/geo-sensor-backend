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


class WorkspaceRole(str, enum.Enum):
    """Workspace member roles."""
    ADMIN = "admin"
    USER = "user"


class CampaignStatus(str, enum.Enum):
    """Campaign lifecycle status."""
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class QueryType(str, enum.Enum):
    """Query classification type."""
    ANCHOR = "anchor"
    EXPLORATION = "exploration"


class TriggerType(str, enum.Enum):
    """Campaign run trigger type."""
    SCHEDULED = "scheduled"
    MANUAL = "manual"


class RunStatus(str, enum.Enum):
    """Campaign run execution status."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class OperationType(str, enum.Enum):
    """Operation log types."""
    PROMOTE_TO_ANCHOR = "promote_to_anchor"
    ANCHOR_CHANGE_REQUEST = "anchor_change_request"
    PARSER_ISSUE = "parser_issue"
    ARCHIVE = "archive"
    EXPORT = "export"
    LABEL_ACTION = "label_action"


class OperationStatus(str, enum.Enum):
    """Operation status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class LabelType(str, enum.Enum):
    """Response label types."""
    FLAG = "flag"
    QUALITY = "quality"
    CATEGORY = "category"
    CUSTOM = "custom"


class LabelSeverity(str, enum.Enum):
    """Label severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ReviewType(str, enum.Enum):
    """Citation review types."""
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
    CORRECT = "correct"
    UNCERTAIN = "uncertain"


class ComparisonType(str, enum.Enum):
    """Comparison snapshot types."""
    LLM_VS_LLM = "llm_vs_llm"
    DATE_VS_DATE = "date_vs_date"
    VERSION_VS_VERSION = "version_vs_version"
