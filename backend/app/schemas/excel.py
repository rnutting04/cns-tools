# app/schemas/excel.py
from pydantic import BaseModel


class ReserveScheduleIssue(BaseModel):
    sheet: str  # association code (one tab per association)
    group: str  # heading the component sits under, e.g. "SIRS Non-Waivable"; "" if none
    cell: str  # e.g. "H10"
    row: int
    code: str  # GL code, e.g. "7061"
    description: str
    balance: float | None  # None when the cell isn't a number
    problem: str  # "negative" | "not_a_number"


class ReserveScheduleSheet(BaseModel):
    name: str
    line_items: int
    issue_count: int
    checked: bool  # False: no Balance header found on the tab


class ReserveScheduleReport(BaseModel):
    filename: str
    sheet_count: int
    line_items: int
    issues: list[ReserveScheduleIssue]
    sheets: list[ReserveScheduleSheet]
