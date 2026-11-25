# app/routers/financials.py
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pdfminer.pdfparser import PDFSyntaxError
from pdfplumber.utils.exceptions import PdfminerException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.financials import FinancialCheckReport
from app.services.audit import log_event
from app.services.financials.report import build_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/financials", tags=["financials"])

MAX_PDF_BYTES = 40 * 1024 * 1024  # sample packets are 6-8 MB


@router.post("/check", response_model=FinancialCheckReport)
def check_financials(
    financial_report: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FinancialCheckReport:
    """
    Run the month-end reconciliation checks on a financial packet PDF.

    Synchronous and stateless: the PDF is read in memory and not stored.
    Takes a few seconds per packet (declared ``def`` so FastAPI runs it in
    the threadpool rather than blocking the event loop).
    """
    data = financial_report.file.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF is larger than 40 MB.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail="File is not a PDF.")

    filename = financial_report.filename or "financials.pdf"
    try:
        report = build_report(data, filename)
    except (PdfminerException, PDFSyntaxError, ValueError) as exc:
        logger.warning("financial check failed for %s: %s", filename, exc)
        raise HTTPException(
            status_code=422, detail="Could not read this PDF's financial reports."
        ) from exc

    log_event(
        db,
        actor=current_user,
        action="financials.check.run",
        target_type="financial_packet",
        metadata={"filename": filename, "summary": report.summary},
    )
    db.commit()
    return report
