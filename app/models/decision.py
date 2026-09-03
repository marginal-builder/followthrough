
from sqlmodel import Field, SQLModel


class Decision(SQLModel, table=True):
    __tablename__ = "decisions"

    id: int | None = Field(default=None, primary_key=True)
    board_id: int = Field(
        default=None,
        foreign_key="weekly_boards.id",
        ondelete="CASCADE",
        nullable=False,
    )
    body: str = Field(nullable=False)
