# app/routers/financials.py
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.financials import (
    FinancialCheckReport,
    FinancialEvidenceRegion,
    FinancialEvidenceResponse,
)
from app.services.audit import log_event
from app.services.financials.pdf import PDF_ERRORS as _PDF_ERRORS
from app.services.financials.pdf import BBox
from app.services.financials.report import build_report, render_evidence

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/financials", tags=["financials"])

MAX_PDF_BYTES = 40 * 1024 * 1024  # sample packets are 6-10 MB
# A packet yields ~30 regions; this only guards against abuse.
MAX_REGIONS = 200

_regions_adapter = TypeAdapter(list[FinancialEvidenceRegion])


def _read_pdf(upload: UploadFile) -> bytes:
    data = upload.file.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF is larger than 40 MB.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail="File is not a PDF.")
    return data


@router.post("/check", response_model=FinancialCheckReport)
def check_financials(
    financial_report: UploadFile = File(...),
    images: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FinancialCheckReport:
    """
    Run the month-end reconciliation checks on a financial packet PDF.

    Synchronous and stateless: the PDF is read in memory and not stored.
    Takes a few seconds per packet (declared ``def`` so FastAPI runs it in
    the threadpool rather than blocking the event loop).

    ``images=false`` skips the highlighted screenshots (each side still has
    ``page`` + ``bbox``); fetch them later from ``/evidence``.
    """
    data = _read_pdf(financial_report)
    filename = financial_report.filename or "financials.pdf"
    try:
        report = build_report(data, filename, images=images)
    except _PDF_ERRORS as exc:
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


@router.post("/evidence", response_model=FinancialEvidenceResponse)
def financial_evidence(
    financial_report: UploadFile = File(...),
    regions: str = Form(..., description="JSON list of {page, bbox: [x0, top, x1, bottom]}"),
    current_user: User = Depends(get_current_user),
) -> FinancialEvidenceResponse:
    """
    Render highlighted screenshots of regions of a packet: the evidence for
    a report fetched with ``images=false``. Re-uploads the same PDF (the
    server keeps nothing) but skips re-running the checks.
    """
    try:
        parsed = _regions_adapter.validate_json(regions)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Invalid regions.") from exc
    if len(parsed) > MAX_REGIONS:
        raise HTTPException(status_code=422, detail=f"At most {MAX_REGIONS} regions.")

    data = _read_pdf(financial_report)
    try:
        images = render_evidence(data, [(r.page, BBox(*r.bbox)) for r in parsed])
    except _PDF_ERRORS as exc:
        logger.warning("evidence render failed for %s: %s", financial_report.filename, exc)
        raise HTTPException(status_code=422, detail="Could not read this PDF.") from exc
    return FinancialEvidenceResponse(images=images)
