# app/routers/excel.py
import io
import logging
import zipfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.excel import (
    ReserveScheduleIssue,
    ReserveScheduleReport,
    ReserveScheduleSheet,
)
from app.services.audit import log_event
from app.services.excel.reserve_schedule import check_workbook

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/excel", tags=["excel"])

MAX_XLSX_BYTES = 25 * 1024 * 1024  # the MASS workbook is ~1 MB


@router.post("/reserve-schedule/check", response_model=ReserveScheduleReport)
def check_reserve_schedule(
    workbook: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReserveScheduleReport:
    """
    Flag reserve schedule line items whose Balance is negative.

    Synchronous and stateless: the workbook is read in memory and not stored.
    """
    data = workbook.file.read(MAX_XLSX_BYTES + 1)
    if len(data) > MAX_XLSX_BYTES:
        raise HTTPException(status_code=413, detail="Workbook is larger than 25 MB.")
    # .xlsx/.xlsm are zip archives; old binary .xls is not supported by openpyxl.
    if not data.startswith(b"PK"):
        raise HTTPException(
            status_code=422, detail="File is not an .xlsx workbook. Save it as .xlsx and retry."
        )

    filename = workbook.filename or "workbook.xlsx"
    try:
        result = check_workbook(io.BytesIO(data))
    except (InvalidFileException, zipfile.BadZipFile, KeyError, ValueError) as exc:
        logger.warning("reserve schedule check failed for %s: %s", filename, exc)
        raise HTTPException(status_code=422, detail="Could not read this workbook.") from exc

    issues = [
        ReserveScheduleIssue(
            sheet=i.sheet,
            group=i.group,
            cell=i.cell,
            row=i.row,
            code=i.code,
            description=i.description,
            balance=float(i.balance) if i.balance is not None else None,
            problem=i.problem,
        )
        for i in result.issues
    ]
    report = ReserveScheduleReport(
        filename=filename,
        sheet_count=len(result.sheets),
        line_items=sum(s.line_items for s in result.sheets),
        issues=issues,
        sheets=[
            ReserveScheduleSheet(
                name=s.name, line_items=s.line_items, issue_count=len(s.issues), checked=s.checked
            )
            for s in result.sheets
        ],
    )

    log_event(
        db,
        actor=current_user,
        action="excel.reserve_schedule.check",
        target_type="reserve_schedule_workbook",
        metadata={"filename": filename, "sheets": report.sheet_count, "issues": len(issues)},
    )
    db.commit()
    return report
