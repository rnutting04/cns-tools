"""Turn a packet's check results into the API response, with evidence images."""

from __future__ import annotations

import base64
import io
from collections import Counter

from app.schemas.financials import (
    FinancialCheckReport,
    FinancialCheckResult,
    FinancialCheckSide,
)

from . import check_packet
from .checks import CheckResult, Side, Status
from .evidence import CropRenderer
from .extract import PageType
from .pdf import BBox

# Most actionable first in the summary; the check list itself keeps the
# business order (banks, AR, prepaids, accrued, reserves, net income).
STATUS_ORDER = [Status.FAIL, Status.REVIEW, Status.MISSING, Status.PASS, Status.NOT_APPLICABLE]


def _data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode()


def _side(side: Side | None, renderer: CropRenderer | None) -> FinancialCheckSide | None:
    if side is None:
        return None
    image = None
    if renderer is not None and side.page and side.bbox:
        image = _data_url(renderer.crop(side.page, side.bbox))
    b = side.bbox
    return FinancialCheckSide(
        source=side.source,
        label=side.label,
        amount=float(side.amount) if side.amount is not None else None,
        page=side.page,
        verified=side.verified,
        guessed=side.guessed,
        bbox=[b.x0, b.top, b.x1, b.bottom] if b and side.page else None,
        image=image,
    )


def _result(r: CheckResult, renderer: CropRenderer | None) -> FinancialCheckResult:
    return FinancialCheckResult(
        id=r.id,
        title=r.title,
        status=r.status.value,
        difference=float(r.difference) if r.difference is not None else None,
        tolerance=float(r.tolerance),
        notes=r.notes,
        left=_side(r.left, renderer),
        right=_side(r.right, renderer),
    )


def build_report(pdf_bytes: bytes, filename: str, images: bool = True) -> FinancialCheckReport:
    """With ``images=False`` the sides carry only ``page`` + ``bbox``; the
    screenshots are ~99% of the response and a third of the time, so a bulk
    session skips them and fetches a packet's with ``render_evidence`` when
    it's opened."""
    packet, results = check_packet(io.BytesIO(pdf_bytes))
    if images:
        with CropRenderer(io.BytesIO(pdf_bytes)) as renderer:
            checks = [_result(r, renderer) for r in results]
    else:
        checks = [_result(r, None) for r in results]
    counts = Counter(r.status for r in results)
    found = sorted({t.value for t in packet.page_types.values() if t is not PageType.OTHER})
    return FinancialCheckReport(
        filename=filename,
        page_count=len(packet.page_types),
        reports_found=found,
        summary={s.value: counts.get(s, 0) for s in STATUS_ORDER},
        checks=checks,
    )


def render_evidence(pdf_bytes: bytes, regions: list[tuple[int, BBox]]) -> list[str | None]:
    """Highlighted crops for (page, bbox) regions, in order. A region on a
    page the PDF doesn't have yields None rather than failing the batch."""
    out: list[str | None] = []
    with CropRenderer(io.BytesIO(pdf_bytes)) as renderer:
        for page, bbox in regions:
            try:
                out.append(_data_url(renderer.crop(page, bbox)))
            except IndexError:
                out.append(None)
    return out
