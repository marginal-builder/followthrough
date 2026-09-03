from datetime import date

from sqlmodel import Field, SQLModel


class WeeklyBoard(SQLModel, table=True):
    __tablename__ = "weekly_boards"

    id: int | None = Field(default=None, primary_key=True)
    week_start: date = Field(unique=True, nullable=False)
    is_archived: bool = Field(default=False)
