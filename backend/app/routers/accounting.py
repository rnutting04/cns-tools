# app/routers/accounting.py
"""Standalone accounting tools (separate from the financial packet review):

- revenue threshold: which year-end report (compilation / review / audit)
  an association needs, from its income & expense TOTAL REVENUES;
- FDIC exposure: balances per bank from the balance sheet, flagged at $250k.

Both take a PDF (a full packet or just the relevant report), are stateless,
and reuse the packet reader, so OCR damage handling and the OCR fallback for
PDFs without a text layer apply here too.
"""

import io
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pdfminer.pdfparser import PDFSyntaxError
from pdfplumber.utils.exceptions import PdfminerException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.accounting import (
    FdicAccount,
    FdicInstitution,
    FdicReport,
    RevenueBasisOut,
    RevenueThresholdReport,
    SourceFigure,
)
from app.services.audit import log_event
from app.services.financials.extract import Packet, Value, extract_packet
from app.services.financials.fdic import Account, fdic_exposure
from app.services.financials.ocr import ocr_available
from app.services.financials.pdf import Page, load_pages
from app.services.financials.thresholds import RevenueBasis, revenue_tier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/accounting", tags=["accounting"])

MAX_PDF_BYTES = 40 * 1024 * 1024
_PDF_ERRORS = (PdfminerException, PDFSyntaxError, ValueError)


def _load(upload: UploadFile) -> tuple[str, list[Page], Packet]:
    data = upload.file.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF is larger than 40 MB.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail="File is not a PDF.")
    filename = upload.filename or "report.pdf"
    try:
        pages = load_pages(io.BytesIO(data))
    except _PDF_ERRORS as exc:
        logger.warning("accounting tool could not read %s: %s", filename, exc)
        raise HTTPException(status_code=422, detail="Could not read this PDF.") from exc
    if not any(p.words for p in pages):
        detail = "This PDF has no readable text."
        if not ocr_available():
            detail += " It was likely saved with Print to PDF; OCR isn't installed on this server."
        raise HTTPException(status_code=422, detail=detail)
    return filename, pages, extract_packet(pages)


def _figure(v: Value | None) -> SourceFigure | None:
    if v is None:
        return None
    b = v.bbox
    return SourceFigure(
        label=v.label,
        amount=float(v.amount),
        page=v.page,
        bbox=[b.x0, b.top, b.x1, b.bottom],
        verified=v.verified,
        guessed=v.guessed,
    )


def _basis(b: RevenueBasis) -> RevenueBasisOut:
    return RevenueBasisOut(
        operating=_figure(b.operating),
        reserve=_figure(b.reserve),
        total=float(b.total) if b.total is not None else None,
        tier=b.tier.value if b.tier else None,
        notes=b.notes,
    )


def _account(a: Account) -> FdicAccount:
    return FdicAccount(
        label=a.label, amount=float(a.amount), network=a.network, source=_figure(a.value)
    )


@router.post("/revenue-threshold", response_model=RevenueThresholdReport)
def revenue_threshold(
    report: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RevenueThresholdReport:
    """Which year-end report the association needs, from operating + reserve
    TOTAL REVENUES (Year-to-Date Actual, and the Annual column)."""
    filename, pages, packet = _load(report)
    if not packet.income_expense:
        raise HTTPException(status_code=422, detail="No income & expense report found in this PDF.")
    result = revenue_tier(packet)
    out = RevenueThresholdReport(
        filename=filename,
        page_count=len(pages),
        ocr_pages=sum(p.ocr for p in pages),
        ytd_actual=_basis(result.ytd_actual),
        annual=_basis(result.annual),
    )
    log_event(
        db,
        actor=current_user,
        action="accounting.revenue_threshold.run",
        target_type="income_expense_report",
        metadata={
            "filename": filename,
            "ytd_tier": out.ytd_actual.tier,
            "annual_tier": out.annual.tier,
        },
    )
    db.commit()
    return out


@router.post("/fdic", response_model=FdicReport)
def fdic(
    report: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FdicReport:
    """Balances per bank from the balance sheet; $250,000 or more is flagged."""
    filename, pages, packet = _load(report)
    bs = packet.balance_sheet
    if bs is None:
        out = FdicReport(
            filename=filename,
            page_count=len(pages),
            ocr_pages=sum(p.ocr for p in pages),
            limit=250000.0,
            balance_sheet_found=False,
            institutions=[],
            unrecognized=[],
        )
    else:
        result = fdic_exposure(bs)
        out = FdicReport(
            filename=filename,
            page_count=len(pages),
            ocr_pages=sum(p.ocr for p in pages),
            limit=float(result.limit),
            balance_sheet_found=True,
            institutions=[
                FdicInstitution(
                    name=i.name,
                    total=float(i.total),
                    over_limit=i.over_limit,
                    accounts=[_account(a) for a in i.accounts],
                    notes=i.notes,
                )
                for i in result.institutions
            ],
            unrecognized=[_account(a) for a in result.unrecognized],
        )
    log_event(
        db,
        actor=current_user,
        action="accounting.fdic.run",
        target_type="balance_sheet",
        metadata={
            "filename": filename,
            "over_limit": [i.name for i in out.institutions if i.over_limit],
        },
    )
    db.commit()
    return out
