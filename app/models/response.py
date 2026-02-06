from typing import TYPE_CHECKING

from sqlalchemy import JSON, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import LLMProvider

if TYPE_CHECKING:
    from app.models.citation import Citation
    from app.models.query import Query


class Response(Base, TimestampMixin):
    __tablename__ = "responses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    llm_provider: Mapped[LLMProvider] = mapped_column(Enum(LLMProvider), nullable=False)
    # e.g., "gpt-4", "gemini-pro"
    llm_model: Mapped[str] = mapped_column(String(100), nullable=False)

    # Analysis results (populated after analysis)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # -1.0 to 1.0
    # positive, negative, neutral
    sentiment_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # recommendation, comparison, mention, negative
    context_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    geo_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100
    geo_grade: Mapped[str | None] = mapped_column(String(2), nullable=True)  # A, B, C, D, F
    # {trigger_name: bool}
    geo_triggers: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    query_id: Mapped[int] = mapped_column(ForeignKey("queries.id"), nullable=False)

    # Relationships
    query: Mapped["Query"] = relationship("Query", back_populates="responses")
    citations: Mapped[list["Citation"]] = relationship(
        "Citation", back_populates="response", cascade="all, delete-orphan"
    )
