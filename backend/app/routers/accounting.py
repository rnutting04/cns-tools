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
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pdfminer.pdfparser import PDFSyntaxError
from pdfplumber.utils.exceptions import PdfminerException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.accounting_job import AccountingJob
from app.models.letter_job import JobStatus
from app.models.user import User, UserRole
from app.schemas.accounting import (
    AccountingJobDetail,
    AccountingJobResult,
    AccountingJobSummary,
    FdicAccount,
    FdicInstitution,
    FdicReport,
    RevenueBasisOut,
    RevenueThresholdReport,
    SourceFigure,
)
from app.services.audit import log_event
from app.services.financials.batch import TOOLS
from app.services.financials.extract import Packet, Value, extract_packet
from app.services.financials.fdic import Account, fdic_exposure
from app.services.financials.ocr import ocr_available
from app.services.financials.pdf import Page, load_pages
from app.services.financials.tasks import run_accounting_job
from app.services.financials.thresholds import RevenueBasis, revenue_tier
from app.services.storage import storage_service

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


# --------------------------------------------------------------------------
# Background jobs: combined multi-association PDFs
# --------------------------------------------------------------------------

# A combined file of ~180 balance sheets is ~22 MB.
MAX_JOB_PDF_BYTES = 100 * 1024 * 1024


def _summary(job: AccountingJob) -> dict:
    results = job.results or []
    return {
        "id": str(job.id),
        "tool": job.tool,
        "filename": job.filename,
        "status": job.status.value,
        "total_pages": job.total_pages,
        "pages_done": job.pages_done or 0,
        "current_association": job.current_association,
        "associations_done": len(results),
        "flagged_count": sum(1 for r in results if r.get("flagged")),
        "error_detail": job.error_detail,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
    }


def _own_job(db: Session, job_id: str, user: User) -> AccountingJob:
    try:
        parsed = uuid.UUID(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc
    job = db.query(AccountingJob).filter(AccountingJob.id == parsed).first()
    if job is None or (job.created_by != user.id and user.role != UserRole.super_admin):
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.post("/jobs", response_model=AccountingJobSummary, status_code=202)
def start_job(
    tool: str = Form(...),
    report: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AccountingJobSummary:
    """Run a tool over a combined PDF (any number of associations) in the
    background. Poll GET /accounting/jobs/{id} for progress and results."""
    if tool not in TOOLS:
        raise HTTPException(status_code=422, detail=f"Unknown tool: {tool}")
    data = report.file.read(MAX_JOB_PDF_BYTES + 1)
    if len(data) > MAX_JOB_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF is larger than 100 MB.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail="File is not a PDF.")

    job_id = uuid.uuid4()
    filename = report.filename or "report.pdf"
    key = f"accounting/{job_id}/input.pdf"
    storage_service.upload_file(data, key, content_type="application/pdf")
    job = AccountingJob(
        id=job_id,
        tool=tool,
        filename=filename,
        input_path=key,
        results=[],
        pages_done=0,
        status=JobStatus.pending,
        created_by=current_user.id,
    )
    db.add(job)
    log_event(
        db,
        actor=current_user,
        action=f"accounting.{tool}.job",
        target_type="accounting_job",
        target_id=str(job_id),
        metadata={"filename": filename},
    )
    db.commit()
    run_accounting_job.delay(str(job_id))
    db.refresh(job)
    return AccountingJobSummary(**_summary(job))


@router.get("/jobs", response_model=list[AccountingJobSummary])
def list_jobs(
    tool: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AccountingJobSummary]:
    """Your 20 most recent runs (optionally of one tool), newest first."""
    q = db.query(AccountingJob).filter(AccountingJob.created_by == current_user.id)
    if tool:
        q = q.filter(AccountingJob.tool == tool)
    jobs = q.order_by(AccountingJob.created_at.desc()).limit(20).all()
    return [AccountingJobSummary(**_summary(j)) for j in jobs]


@router.get("/jobs/{job_id}", response_model=AccountingJobDetail)
def get_job(
    job_id: str,
    since: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AccountingJobDetail:
    """Progress and results. ``since`` returns only results after the first
    ``since`` (associations finished since the last poll)."""
    job = _own_job(db, job_id, current_user)
    return AccountingJobDetail(
        **_summary(job),
        results=[AccountingJobResult(**r) for r in (job.results or [])[max(since, 0) :]],
    )
