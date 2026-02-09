import enum
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.response import Response


class QueryStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Query(Base, TimestampMixin):
    __tablename__ = "queries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(50), default=QueryStatus.PENDING.value, nullable=False
    )
    project_id: Mapped[int] = mapped_column(
        sa.ForeignKey("projects.id"), nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="queries")
    responses: Mapped[list["Response"]] = relationship(
        "Response", back_populates="query", cascade="all, delete-orphan"
    )
