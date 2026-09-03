from datetime import UTC, datetime

from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel


class FeedbackItem(SQLModel, table=True):
    __tablename__ = "feedback_items"
    __table_args__ = (
        CheckConstraint(
            '"column" IN (\'start\', \'stop\', \'continue\')',
            name="feedback_item_column_check",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    board_id: int = Field(
        default=None,
        foreign_key="weekly_boards.id",
        ondelete="CASCADE",
        nullable=False,
    )
    column: str = Field(nullable=False)
    body: str = Field(nullable=False)
    author_id: int | None = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )
