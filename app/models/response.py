from sqlalchemy import String, ForeignKey, Text, Float, JSON, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from typing import TYPE_CHECKING

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.query import Query
    from app.models.citation import Citation


class LLMProvider(str, enum.Enum):
    OPENAI = "openai"
    GEMINI = "gemini"


class Response(Base, TimestampMixin):
    __tablename__ = "responses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    llm_provider: Mapped[LLMProvider] = mapped_column(Enum(LLMProvider), nullable=False)
    llm_model: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "gpt-4", "gemini-pro"

    # Analysis results (populated after analysis)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # -1.0 to 1.0
    sentiment_label: Mapped[str | None] = mapped_column(String(50), nullable=True)  # positive, negative, neutral
    context_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # recommendation, comparison, mention, negative
    geo_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100
    geo_grade: Mapped[str | None] = mapped_column(String(2), nullable=True)  # A, B, C, D, F
    geo_triggers: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {trigger_name: bool}

    query_id: Mapped[int] = mapped_column(ForeignKey("queries.id"), nullable=False)

    # Relationships
    query: Mapped["Query"] = relationship("Query", back_populates="responses")
    citations: Mapped[list["Citation"]] = relationship("Citation", back_populates="response", cascade="all, delete-orphan")
