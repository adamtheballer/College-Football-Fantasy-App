from pydantic import BaseModel


class SchedulePreview(BaseModel):
    week: int
    opponent: str
    home_away: str
    grade: str


class SchedulePreviewList(BaseModel):
    data: list[SchedulePreview]
