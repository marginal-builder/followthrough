from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import JSON, CheckConstraint
from sqlmodel import Column, Field, SQLModel


class Extraction(SQLModel, table=True):
    __tablename__ = "extractions"
    __table_args__ = (
        CheckConstraint("kind IN ('action', 'decision')", name="extraction_kind_check"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'discarded')",
            name="extraction_status_check",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    board_id: int = Field(
        default=None,
        foreign_key="weekly_boards.id",
        ondelete="CASCADE",
        nullable=False,
    )
    kind: str = Field(nullable=False)
    payload: Any = Field(sa_column=Column(JSON, nullable=False))
    status: str = Field(default="pending", nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )


class ActionSuggestion(BaseModel):
    body: str
    owner_hint: str | None = None
    due_date: str | None = None


class DecisionSuggestion(BaseModel):
    body: str


class ExtractionResult(BaseModel):
    actions: list[ActionSuggestion]
    decisions: list[DecisionSuggestion]
