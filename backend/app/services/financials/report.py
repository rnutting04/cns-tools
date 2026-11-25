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

# Most actionable first in the summary; the check list itself keeps the
# business order (banks, AR, prepaids, accrued, reserves, net income).
STATUS_ORDER = [Status.FAIL, Status.REVIEW, Status.MISSING, Status.PASS, Status.NOT_APPLICABLE]


def _side(side: Side | None, renderer: CropRenderer) -> FinancialCheckSide | None:
    if side is None:
        return None
    image = None
    if side.page and side.bbox:
        png = renderer.crop(side.page, side.bbox)
        image = "data:image/png;base64," + base64.b64encode(png).decode()
    return FinancialCheckSide(
        source=side.source,
        label=side.label,
        amount=float(side.amount) if side.amount is not None else None,
        page=side.page,
        verified=side.verified,
        guessed=side.guessed,
        image=image,
    )


def _result(r: CheckResult, renderer: CropRenderer) -> FinancialCheckResult:
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


def build_report(pdf_bytes: bytes, filename: str) -> FinancialCheckReport:
    packet, results = check_packet(io.BytesIO(pdf_bytes))
    with CropRenderer(io.BytesIO(pdf_bytes)) as renderer:
        checks = [_result(r, renderer) for r in results]
    counts = Counter(r.status for r in results)
    found = sorted({t.value for t in packet.page_types.values() if t is not PageType.OTHER})
    return FinancialCheckReport(
        filename=filename,
        page_count=len(packet.page_types),
        reports_found=found,
        summary={s.value: counts.get(s, 0) for s in STATUS_ORDER},
        checks=checks,
    )
