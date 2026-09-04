from datetime import UTC, datetime

from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel


class Transcript(SQLModel, table=True):
    __tablename__ = "transcripts"
    __table_args__ = (
        CheckConstraint("status IN ('ready', 'failed')", name="transcript_status_check"),
    )

    id: int | None = Field(default=None, primary_key=True)
    board_id: int = Field(
        default=None,
        foreign_key="weekly_boards.id",
        ondelete="CASCADE",
        nullable=False,
    )
    text: str | None = Field(default=None)
    source: str = Field(default="upload", nullable=False)
    status: str = Field(nullable=False)
    error_message: str | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )
