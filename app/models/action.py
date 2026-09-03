from datetime import date

from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel


class Action(SQLModel, table=True):
    __tablename__ = "actions"
    __table_args__ = (
        CheckConstraint("status IN ('todo', 'in_progress', 'done')", name="action_status_check"),
    )

    id: int | None = Field(default=None, primary_key=True)
    board_id: int = Field(
        default=None,
        foreign_key="weekly_boards.id",
        ondelete="CASCADE",
        nullable=False,
    )
    body: str = Field(nullable=False)
    owner_id: int | None = Field(default=None, foreign_key="users.id")
    status: str = Field(default="todo", nullable=False)
    due_date: date | None = Field(default=None)
