import enum
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.brand import Brand
    from app.models.response import Response


class MatchType(str, enum.Enum):
    EXACT = "exact"
    ALIAS = "alias"
    FUZZY = "fuzzy"
    KEYWORD = "keyword"


class Citation(Base, TimestampMixin):
    __tablename__ = "citations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    matched_text: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    match_type: Mapped[str] = mapped_column(
        sa.String(50),
        default=MatchType.EXACT.value,
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(sa.Float, nullable=False)  # 0.0 to 1.0
    position_start: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    position_end: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    brand_id: Mapped[int] = mapped_column(
        sa.ForeignKey("brands.id"), nullable=False
    )
    response_id: Mapped[int] = mapped_column(
        sa.ForeignKey("responses.id"), nullable=False
    )

    # Relationships
    brand: Mapped["Brand"] = relationship("Brand", back_populates="citations")
    response: Mapped["Response"] = relationship("Response", back_populates="citations")
