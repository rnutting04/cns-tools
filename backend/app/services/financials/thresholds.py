"""Which year-end financial report an association needs, by total revenues.

Total revenues = operating + reserve TOTAL REVENUES from the income &
expense report. Judged twice: on Year-to-Date Actual and on the Annual
(budget) column.

  under $150,000        no additional report
  $150,000 - $299,999   compilation
  $300,000 - $499,999   review
  $500,000 and over     audit
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from .extract import IncomeExpense, Packet, Value


class ReportTier(StrEnum):
    NONE = "none"
    COMPILATION = "compilation"
    REVIEW = "review"
    AUDIT = "audit"


# (lower bound inclusive, tier), highest first.
TIERS: tuple[tuple[Decimal, ReportTier], ...] = (
    (Decimal("500000"), ReportTier.AUDIT),
    (Decimal("300000"), ReportTier.REVIEW),
    (Decimal("150000"), ReportTier.COMPILATION),
)


def tier_for(revenue: Decimal) -> ReportTier:
    return next((t for floor, t in TIERS if revenue >= floor), ReportTier.NONE)


@dataclass
class RevenueBasis:
    """One column's view: operating + reserve revenues and the tier they imply."""

    operating: Value | None
    reserve: Value | None
    total: Decimal | None
    tier: ReportTier | None
    notes: list[str] = field(default_factory=list)


@dataclass
class RevenueTierResult:
    ytd_actual: RevenueBasis
    annual: RevenueBasis
    departments: list[str]  # which I&E reports were found


def _basis(ie: dict[str, IncomeExpense], attr: str, what: str) -> RevenueBasis:
    op = getattr(ie["operating"], attr) if "operating" in ie else None
    rs = getattr(ie["reserve"], attr) if "reserve" in ie else None
    notes: list[str] = []
    if "operating" not in ie:
        notes.append("No operating income & expense report found.")
    elif op is None:
        notes.append(f"Couldn't read operating TOTAL REVENUES ({what}).")
    if "reserve" not in ie:
        notes.append("No reserve income & expense report found; total is operating only.")
    elif rs is None:
        notes.append(f"Couldn't read reserve TOTAL REVENUES ({what}).")
    for v in (op, rs):
        if v is not None and v.guessed:
            notes.append(f"{v.label}: best guess by column position — confirm it.")
    if op is None:
        return RevenueBasis(op, rs, None, None, notes)
    total = op.amount + (rs.amount if rs else Decimal(0))
    return RevenueBasis(op, rs, total, tier_for(total), notes)


def revenue_tier(packet: Packet) -> RevenueTierResult:
    ie = packet.income_expense
    return RevenueTierResult(
        ytd_actual=_basis(ie, "revenue_ytd", "Year-to-Date Actual"),
        annual=_basis(ie, "revenue_annual", "Annual"),
        departments=sorted(ie),
    )
