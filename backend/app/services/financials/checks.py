"""The month-end reconciliation rules, run against an extracted packet.

Status semantics:
  pass            the two figures agree
  fail            they disagree and both were read with confidence
  review          a figure could not be read, or was read but its report's own
                  arithmetic didn't hold (likely OCR) — a human must look
  missing         the supporting report is not in the packet
  not_applicable  the account isn't on the balance sheet and the report is empty
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from .extract import CENT, BankRec, BSRow, Packet, ReportTotal, Value
from .pdf import BBox


class Status(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    REVIEW = "review"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class Side:
    source: str  # which report
    label: str
    amount: Decimal | None
    page: int | None
    bbox: BBox | None
    verified: bool | None

    @classmethod
    def of(cls, source: str, v: Value | None, label: str = "") -> Side:
        if v is None:
            return cls(source, label, None, None, None, None)
        return cls(source, label or v.label, v.amount, v.page, v.bbox, v.verified)


@dataclass
class CheckResult:
    id: str
    title: str
    status: Status
    left: Side | None  # balance sheet / GL side
    right: Side | None  # supporting report side
    difference: Decimal | None = None
    tolerance: Decimal = Decimal("0.00")
    notes: list[str] = field(default_factory=list)


def _compare(
    id: str,
    title: str,
    left: Side,
    right: Side,
    tolerance: Decimal = Decimal("0.00"),
    notes: list[str] | None = None,
) -> CheckResult:
    notes = list(notes or [])
    res = CheckResult(id, title, Status.REVIEW, left, right, tolerance=tolerance, notes=notes)
    if left.amount is None or right.amount is None:
        missing = left if left.amount is None else right
        notes.append(f"Could not read the figure from the {missing.source}.")
        return res
    res.difference = left.amount - right.amount
    if abs(res.difference) <= tolerance + CENT:
        # Two independent reads agreeing is its own confirmation.
        res.status = Status.PASS
        if res.difference and tolerance:
            notes.append(f"Differs by {abs(res.difference):,.2f}, within rounding tolerance.")
        return res
    if left.verified is False or right.verified is False:
        notes.append(
            "Figures disagree, but the report's own totals didn't add up when read — "
            "probably an OCR misread. Check the highlighted area."
        )
        return res
    res.status = Status.FAIL
    if left.verified is None or right.verified is None:
        notes.append("At least one figure had no internal total to confirm the read.")
    return res


def _bs(row: BSRow | None, col: str = "total") -> Value | None:
    return row.amount(col) if row else None


def _schedule_check(
    packet: Packet,
    id: str,
    title: str,
    row: BSRow | None,
    report: ReportTotal | None,
    report_name: str,
    tolerance: Decimal = Decimal("0.00"),
) -> CheckResult:
    left = Side.of("balance sheet", _bs(row), row.label if row else title)
    if report is None:
        if row is None:
            return CheckResult(
                id,
                title,
                Status.NOT_APPLICABLE,
                None,
                None,
                notes=[f"Account is not on the balance sheet and there is no {report_name}."],
            )
        return CheckResult(
            id,
            title,
            Status.MISSING,
            left,
            None,
            notes=[f"No {report_name} page found in the packet."],
        )
    right = Side.of(report_name, report.total)
    if row is None:
        if report.total is not None and report.total.amount == 0:
            return CheckResult(
                id,
                title,
                Status.NOT_APPLICABLE,
                None,
                right,
                notes=["Account is not on the balance sheet and the report total is zero."],
            )
        left = Side("balance sheet", title, Decimal(0), None, None, None)
        return _compare(
            id,
            title,
            left,
            right,
            tolerance,
            ["Account is not on the balance sheet (treated as 0.00)."],
        )
    return _compare(id, title, left, right, tolerance)


def run_checks(packet: Packet) -> list[CheckResult]:
    bs = packet.balance_sheet
    if bs is None:
        return [
            CheckResult(
                "balance_sheet",
                "Balance sheet",
                Status.MISSING,
                None,
                None,
                notes=["No balance sheet page found."],
            )
        ]

    results: list[CheckResult] = []

    # 1 + 9. Each bank account ties to its reconciliation; rec difference is zero.
    recs = {r.last4: r for r in packet.bank_recs if r.last4}
    used: set[str] = set()
    for row in bs.bank_rows:
        last4 = _last4(row.label)
        rec = _match_rec(recs, last4)
        title = f"Bank: {row.label}"
        left = Side.of("balance sheet", _bs(row), row.label)
        if rec is None:
            results.append(
                CheckResult(
                    f"bank:{last4 or row.label}",
                    title,
                    Status.MISSING,
                    left,
                    None,
                    notes=["No bank reconciliation page for this account."],
                )
            )
            continue
        used.add(rec.last4)
        results.append(
            _compare(
                f"bank:{rec.last4}",
                title,
                left,
                Side.of("bank reconciliation", rec.gl_balance, "G/L Balance"),
            )
        )
        diff = rec.balance_difference
        zero_side = Side("expected", "zero", Decimal(0), None, None, True)
        r = _compare(
            f"bank_rec_zero:{rec.last4}",
            f"Bank rec difference is zero: {rec.bank} -{rec.last4}",
            Side.of("bank reconciliation", diff, "G/L and Balance Difference"),
            zero_side,
        )
        results.append(r)
    for last4, rec in recs.items():
        if last4 not in used:
            results.append(
                CheckResult(
                    f"bank_rec_orphan:{last4}",
                    f"Bank rec with no balance sheet account: {rec.bank} -{last4}",
                    Status.REVIEW,
                    None,
                    Side.of("bank reconciliation", rec.gl_balance, "G/L Balance"),
                    notes=[
                        "Reconciliation page doesn't match any bank account on the balance sheet."
                    ],
                )
            )

    # 2. Accounts receivable
    results.append(
        _schedule_check(
            packet,
            "ar",
            "Accounts Receivable (1100)",
            bs.find("1100", ("acctreceivablemembers", "accountsreceivablemembers")),
            packet.ar_aging,
            "AR aging report",
        )
    )
    # 3. Prepaid expenses
    results.append(
        _schedule_check(
            packet,
            "prepaid_expenses",
            "Prepaid Expenses (1150)",
            bs.find("1150", ("prepaidexpense",)),
            packet.prepaid_expenses,
            "Accrued/Prepaid report",
        )
    )
    # 4. Prepaid member assessments
    results.append(
        _schedule_check(
            packet,
            "prepaid_assessments",
            "Prepaid Member Assessments (2100)",
            bs.find("2100", ("prepaidmemberassessment",)),
            packet.prepaid_assessments,
            "prepaid assessment report",
        )
    )
    # 5. Prepaid insurance — schedule is in whole dollars, one rounding per policy.
    ins = packet.insurance
    tol = Decimal("0.50") * max(ins.rows, 1) if ins and ins.whole_dollars else Decimal(0)
    results.append(
        _schedule_check(
            packet,
            "prepaid_insurance",
            "Prepaid Insurance (1130)",
            bs.find("1130", ("prepaidinsurance",)),
            ins,
            "insurance schedule",
            tolerance=tol,
        )
    )
    # 6. Accrued expenses
    results.append(
        _schedule_check(
            packet,
            "accrued_expenses",
            "Accrued Expenses (2015)",
            bs.find("2015", ("accruedexpense",)),
            packet.accrued,
            "Accrued/Prepaid report",
        )
    )

    # 7. Reserve assets vs reserve schedule
    total_assets = next((r for r in bs.rows if r.key == "totalassets"), None)
    left = Side.of("balance sheet", _bs(total_assets, "reserve"), "Total Assets — Reserve")
    if packet.reserve_schedule is None:
        results.append(
            CheckResult(
                "reserve_schedule",
                "Reserve assets vs reserve schedule",
                Status.MISSING,
                left,
                None,
                notes=["No reserve schedule page found in the packet."],
            )
        )
    else:
        results.append(
            _compare(
                "reserve_schedule",
                "Reserve assets vs reserve schedule",
                left,
                Side.of("reserve schedule", packet.reserve_schedule.total),
            )
        )

    # 10. Net income, one per department
    net = next((r for r in bs.rows if r.key.startswith("totalnetincome")), None)
    for dept in ("operating", "reserve"):
        title = f"Net Income — {dept.title()}"
        left = Side.of("balance sheet", _bs(net, dept), f"Total Net Income — {dept.title()}")
        ie = packet.income_expense.get(dept)
        if ie is None:
            results.append(
                CheckResult(
                    f"net_income:{dept}",
                    title,
                    Status.MISSING,
                    left,
                    None,
                    notes=[f"No {dept} income & expense report found."],
                )
            )
            continue
        notes = [ie.ytd_net.note] if ie.ytd_net and ie.ytd_net.note else []
        results.append(
            _compare(
                f"net_income:{dept}",
                title,
                left,
                Side.of("income & expense report", ie.ytd_net),
                notes=notes,
            )
        )

    return results


def _last4(label: str) -> str | None:
    m = re.search(r"-\s*(\d{3,4})\s*$", label)
    return m.group(1) if m else None


def _match_rec(recs: dict[str, BankRec], last4: str | None) -> BankRec | None:
    # Exact match only: WPK has both "-2695" and "ICS - 695", so suffix
    # matching would tie the ICS account to the wrong reconciliation.
    return recs.get(last4) if last4 else None
