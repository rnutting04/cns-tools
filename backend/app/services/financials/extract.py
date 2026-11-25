"""Locate each report in a monthly financial packet and read the figures the
reconciliation checks need.

No LLM: every report in the packet is a fixed-format CSC/Accounting export,
so pages are classified by their title and figures are read by label.

OCR confidence comes from arithmetic, not from the OCR engine. Each report
carries internal identities (rows sum to their total, aging buckets sum to
the balance, ``actual - budget == variance``...). A value that participates
in an identity that holds is marked ``verified=True``; one in an identity
that fails is ``verified=False`` and its check is routed to human review
instead of being reported as a mismatch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from .pdf import BBox, Line, Page, group_lines, parse_amounts, parse_whole_amounts, squash

CENT = Decimal("0.005")


class PageType(StrEnum):
    BALANCE_SHEET = "balance_sheet"
    INCOME_EXPENSE = "income_expense"
    BANK_REC = "bank_rec"
    AR_AGING = "ar_aging"
    PREPAID_ASSESSMENTS = "prepaid_assessments"
    ACCRUED_PREPAID = "accrued_prepaid"
    INSURANCE_SCHEDULE = "insurance_schedule"
    RESERVE_SCHEDULE = "reserve_schedule"
    CHECK_REGISTER = "check_register"
    OTHER = "other"


def classify(page: Page) -> PageType:
    h = page.header_key(8)
    if "bankreconciliation" in h:
        return PageType.BANK_REC
    if "balancesheet" in h:
        return PageType.BALANCE_SHEET
    # MOR's first I&E page lost its title in OCR; the column header survives.
    if "incomeandexpense" in h or ("currentmonth" in h and "yeartodate" in h):
        return PageType.INCOME_EXPENSE
    if "scheduleofinsurance" in h:
        return PageType.INSURANCE_SCHEDULE
    if "reserveschedule" in h:
        return PageType.RESERVE_SCHEDULE
    if "accruedprepaid" in h:
        return PageType.ACCRUED_PREPAID
    # Title words can land on different OCR lines ("NAMES" above "CSC AR"),
    # so also accept the words anywhere in the header, in any order.
    if "arnames" in h or {"ar", "names"} <= page.header_words(8):
        return PageType.AR_AGING
    if "cscprepaid" in h:
        return PageType.PREPAID_ASSESSMENTS
    if "checkregister" in h:
        return PageType.CHECK_REGISTER
    return PageType.OTHER


# --------------------------------------------------------------------------
# Values and identities
# --------------------------------------------------------------------------


@dataclass
class Value:
    amount: Decimal
    page: int
    bbox: BBox
    label: str
    verified: bool | None = None  # None = no identity covers this value
    note: str = ""


@dataclass
class Identity:
    description: str
    ok: bool
    page: int


def _settle(
    identities: list[Identity],
    description: str,
    lhs: Decimal,
    rhs: Decimal,
    values: list[Value],
    page: int,
) -> bool:
    ok = abs(lhs - rhs) < CENT
    identities.append(Identity(description, ok, page))
    for v in values:
        if not ok:
            v.verified = False
        elif v.verified is None:
            v.verified = True
    return ok


def _amounts_on(line: Line, page: Page, label: str) -> list[Value]:
    return [Value(a, page.number, line.bbox, label) for a in parse_amounts(line.text)]


# --------------------------------------------------------------------------
# Balance sheet
# --------------------------------------------------------------------------

COLUMNS = ("operating", "reserve", "total")


@dataclass
class BSRow:
    label: str
    code: str | None
    section: str
    bbox: BBox
    values: dict[str, Value] = field(default_factory=dict)
    conflicts: list[Value] = field(default_factory=list)

    @property
    def key(self) -> str:
        return squash(self.label)

    def amount(self, col: str = "total") -> Value | None:
        if col in self.values:
            return self.values[col]
        # Single-department rows sometimes print only the department column.
        if col == "total":
            dept = [v for c, v in self.values.items() if c != "total"]
            if len(dept) == 1:
                return dept[0]
        return None


@dataclass
class BalanceSheet:
    page: int
    rows: list[BSRow]
    identities: list[Identity]

    def find(self, code: str | None = None, keys: tuple[str, ...] = ()) -> BSRow | None:
        for row in self.rows:
            if code and row.code == code:
                return row
        for row in self.rows:
            if row.values and any(k in row.key for k in keys):
                return row
        return None

    @property
    def bank_rows(self) -> list[BSRow]:
        return [
            r
            for r in self.rows
            if r.section == "bank" and r.values and not r.key.startswith("total")
        ]


_CODE_RE = re.compile(r"^(\d{4}(?:\.[A-Z]{1,3})?)(?=\s|$)")


def parse_balance_sheet(page: Page) -> BalanceSheet:
    header = next(
        (
            ln
            for ln in page.lines
            if {"operating", "reserve", "total"} <= set(ln.text.lower().split())
        ),
        None,
    )
    if header is None:
        raise ValueError(f"page {page.number}: balance sheet column header not found")
    centers = {w.text.lower(): w.bbox.cx for w in header.words if w.text.lower() in COLUMNS}
    label_limit = min(w.bbox.x0 for w in header.words if w.text.lower() in COLUMNS) - 12
    body = [w for w in page.words if w.bbox.top > header.bbox.bottom]

    label_lines = group_lines([w for w in body if w.bbox.x1 < label_limit])
    rows: list[BSRow] = []
    section = ""
    for ln in label_lines:
        text = ln.text
        m = _CODE_RE.match(text)
        rows.append(BSRow(label=text, code=m.group(1) if m else None, section="", bbox=ln.bbox))

    # Values are placed by geometry: nearest label row vertically, nearest
    # column header horizontally. The OCR line order is not used at all.
    for w in body:
        if w.bbox.x0 < label_limit - 10:
            continue
        amounts = parse_amounts(w.text)
        if not amounts or not rows:
            continue
        width = (w.bbox.x1 - w.bbox.x0) / len(amounts)
        for i, amt in enumerate(amounts):
            box = BBox(
                w.bbox.x0 + i * width, w.bbox.top, w.bbox.x0 + (i + 1) * width, w.bbox.bottom
            )
            row = min(rows, key=lambda r: abs(r.bbox.cy - box.cy))
            if abs(row.bbox.cy - box.cy) > 14:
                continue
            col = min(centers, key=lambda c: abs(centers[c] - box.cx))
            val = Value(amt, page.number, row.bbox.union(box), row.label)
            if col in row.values:
                row.conflicts.append(val)
            else:
                row.values[col] = val

    for row in rows:
        if not row.values and not row.key.startswith("total"):
            section = row.key
        row.section = section

    identities: list[Identity] = []
    for row in rows:
        parts = [row.values[c] for c in ("operating", "reserve") if c in row.values]
        if "total" in row.values and parts:
            _settle(
                identities,
                f"{row.label}: operating + reserve = total",
                sum((p.amount for p in parts), Decimal(0)),
                row.values["total"].amount,
                [*parts, row.values["total"]],
                page.number,
            )
        if row.conflicts:
            for v in [*row.values.values(), *row.conflicts]:
                v.verified = False
                v.note = "two amounts read into the same cell"

    sheet = BalanceSheet(page.number, rows, identities)

    bank_total = next((r for r in rows if r.key.startswith("totalbank")), None)
    if bank_total:
        for col in COLUMNS:
            parts = [r.values[col] for r in sheet.bank_rows if col in r.values]
            if col in bank_total.values and parts:
                _settle(
                    identities,
                    f"bank accounts sum to Total Bank ({col})",
                    sum((p.amount for p in parts), Decimal(0)),
                    bank_total.values[col].amount,
                    [*parts, bank_total.values[col]],
                    page.number,
                )

    assets = next((r for r in rows if r.key == "totalassets"), None)
    l_and_e = next((r for r in rows if r.key.startswith("totalliabilities")), None)
    if assets and l_and_e:
        for col in COLUMNS:
            if col in assets.values and col in l_and_e.values:
                _settle(
                    identities,
                    f"Total Assets = Total Liabilities & Equity ({col})",
                    assets.values[col].amount,
                    l_and_e.values[col].amount,
                    [assets.values[col], l_and_e.values[col]],
                    page.number,
                )
    return sheet


# --------------------------------------------------------------------------
# Income & expense
# --------------------------------------------------------------------------


@dataclass
class IncomeExpense:
    department: str  # "operating" | "reserve"
    pages: list[int]
    ytd_net: Value | None
    identities: list[Identity]
    derived: bool = False


def _ie_department(page: Page) -> str | None:
    h = page.header_key(8)
    if "operating" in h:
        return "operating"
    if "reserve" in h:
        return "reserve"
    return None


def parse_income_expense(pages: list[Page], department: str) -> IncomeExpense:
    """Read YTD net income. Rows carry 7 amounts: month actual/budget/variance,
    YTD actual/budget/variance, annual — so YTD actual is index 3."""
    identities: list[Identity] = []
    excess = revenue = expense = None
    for page in pages:
        for ln in page.lines:
            amounts = _amounts_on(ln, page, ln.text)
            if len(amounts) != 7:
                continue
            label = squash(re.split(r"[\d(]", ln.text, maxsplit=1)[0])
            if label.startswith("excessrevenue"):
                excess = (page, amounts)
            elif label in ("totalrevenues", "revenues"):
                revenue = (page, amounts)
            elif label in ("totalexpenses", "expenses"):
                expense = (page, amounts)

    def variance(row, sign: int, name: str) -> None:
        page, a = row
        for actual, budget, var in ((0, 1, 2), (3, 4, 5)):
            _settle(
                identities,
                f"{department} {name}: variance column",
                sign * (a[actual].amount - a[budget].amount),
                a[var].amount,
                [a[actual], a[budget], a[var]],
                page.number,
            )

    if revenue:
        variance(revenue, 1, "total revenues")
    if expense:
        variance(expense, -1, "total expenses")

    page_nums = [p.number for p in pages]
    if excess:
        variance(excess, 1, "excess revenue/expense")
        ytd = excess[1][3]
        if revenue and expense:
            _settle(
                identities,
                f"{department}: YTD revenues - expenses = excess",
                revenue[1][3].amount - expense[1][3].amount,
                ytd.amount,
                [revenue[1][3], expense[1][3], ytd],
                ytd.page,
            )
        ytd.label = f"{department.title()} YTD Excess Revenue / Expense"
        return IncomeExpense(department, page_nums, ytd, identities)

    if revenue and expense:
        # Excess line missing (MOR's operating I&E ends at TOTAL EXPENSES).
        r, e = revenue[1][3], expense[1][3]
        if r.verified is False or e.verified is False:
            verified = False
        else:
            verified = True if (r.verified and e.verified) else None
        net = Value(
            r.amount - e.amount,
            e.page,
            e.bbox if r.page != e.page else r.bbox.union(e.bbox),
            f"{department.title()} YTD revenues − expenses",
            verified=verified,
            note="Excess Revenue/Expense line not found; derived from YTD totals",
        )
        return IncomeExpense(department, page_nums, net, identities, derived=True)

    return IncomeExpense(department, page_nums, None, identities)


# --------------------------------------------------------------------------
# Bank reconciliation
# --------------------------------------------------------------------------


@dataclass
class BankRec:
    page: int
    bank: str
    last4: str | None
    gl_balance: Value | None
    balance_difference: Value | None
    identities: list[Identity]


_GL_FIX = re.compile(r"G\s*[/I1l|\\]\s*L", re.IGNORECASE)
_BANK_RE = re.compile(r"Bank:\s*(.+?)\s*-\s*(\d{3,4})\b")


def _labeled(lines: list[Line], page: Page, pattern: str) -> Value | None:
    rx = re.compile(pattern, re.IGNORECASE)
    for ln in lines:
        text = _GL_FIX.sub("GL", ln.text)
        m = rx.search(text)
        if m:
            amounts = parse_amounts(text[m.end() :])
            if amounts:
                return Value(amounts[0], page.number, ln.bbox, m.group().strip(" :"))
    return None


def parse_bank_rec(page: Page) -> BankRec:
    lines = page.lines
    m = next((_BANK_RE.search(ln.text) for ln in lines if _BANK_RE.search(ln.text)), None)
    bank = m.group(1) if m else "unknown"
    last4 = m.group(2) if m else None
    start = next((i for i, ln in enumerate(lines) if "reconciliationsummary" in ln.key), 0)
    summary = lines[start:]

    gl = _labeled(summary, page, r"GL\s*Balance:?")
    checks = _labeled(summary, page, r"Uncleared\s*Checks,?\s*Credits:?")
    deposits = _labeled(summary, page, r"Uncleared\s*Deposits,?\s*Debits:?")
    gl_diff = _labeled(summary, page, r"GL\s*Difference:?")
    statement = _labeled(summary, page, r"Statement\s*Balance:?")
    bal_diff = _labeled(summary, page, r"GL\s*and\s*Balance\s*Difference:?")

    identities: list[Identity] = []
    if gl and checks and deposits and gl_diff:
        _settle(
            identities,
            f"{bank}: GL balance + uncleared checks - uncleared deposits = adjusted GL",
            gl.amount + checks.amount - deposits.amount,
            gl_diff.amount,
            [gl, checks, deposits, gl_diff],
            page.number,
        )
    if statement and gl_diff and bal_diff:
        _settle(
            identities,
            f"{bank}: statement balance - adjusted GL = reported difference",
            statement.amount - gl_diff.amount,
            bal_diff.amount,
            [statement, gl_diff, bal_diff],
            page.number,
        )
    return BankRec(page.number, bank, last4, gl, bal_diff, identities)


# --------------------------------------------------------------------------
# Supporting schedules
# --------------------------------------------------------------------------


@dataclass
class ReportTotal:
    """A single reconciling total read from a supporting schedule."""

    kind: PageType
    total: Value | None
    identities: list[Identity]
    whole_dollars: bool = False
    rows: int = 0
    blank: bool = False


def parse_ar_aging(pages: list[Page]) -> ReportTotal:
    identities: list[Identity] = []
    for page in reversed(pages):
        for ln in page.lines:
            if ln.key.startswith("count"):
                a = _amounts_on(ln, page, "AR aging total")
                if not a:
                    continue
                if len(a) == 5:
                    _settle(
                        identities,
                        "AR aging buckets sum to balance",
                        sum((v.amount for v in a[:4]), Decimal(0)),
                        a[4].amount,
                        a,
                        page.number,
                    )
                return ReportTotal(PageType.AR_AGING, a[-1], identities)
    return ReportTotal(PageType.AR_AGING, None, identities)


_ACCOUNT_NO = re.compile(r"\b\d{5}\b")


def parse_prepaid_assessments(pages: list[Page]) -> ReportTotal:
    identities: list[Identity] = []
    rows: list[Value] = []
    total: Value | None = None
    for page in pages:
        for ln in page.lines:
            a = _amounts_on(ln, page, "Prepaid assessment report total")
            if len(a) != 1:
                continue
            rest = re.sub(r"[-\d,.$\s|]", "", ln.text)
            if not rest:
                total = a[0]
            elif _ACCOUNT_NO.search(ln.text):
                rows.append(a[0])
    if total is None:
        return ReportTotal(PageType.PREPAID_ASSESSMENTS, None, identities)
    # Credits print negative; OCR occasionally drops the minus, so sum magnitudes.
    if rows:
        _settle(
            identities,
            "prepaid owner balances sum to report total",
            sum((abs(r.amount) for r in rows), Decimal(0)),
            abs(total.amount),
            [total],
            total.page,
        )
    total.amount = abs(total.amount)
    return ReportTotal(PageType.PREPAID_ASSESSMENTS, total, identities, rows=len(rows))


def parse_accrued_prepaid(page: Page, which: str) -> ReportTotal:
    """``which`` is "prepaid" (GL 1150 section) or "accrued" (GL 2015 section)."""
    identities: list[Identity] = []
    marker = "prepaidinvoices" if which == "prepaid" else "accruedinvoices"
    lines = page.lines
    start = next((i for i, ln in enumerate(lines) if marker in ln.key), None)
    if start is None:
        return ReportTotal(PageType.ACCRUED_PREPAID, None, identities)
    items: list[Value] = []
    for ln in lines[start + 1 :]:
        if ln.key.startswith("total"):
            a = _amounts_on(ln, page, f"Accrued/Prepaid — {which} total")
            if not a:
                # A blank "Total $" means nothing is booked in this section.
                zero = Value(Decimal(0), page.number, ln.bbox, f"Accrued/Prepaid — {which} total")
                zero.note = "total is blank on the report"
                ok = not items
                identities.append(Identity(f"{which} section is empty", ok, page.number))
                zero.verified = ok
                return ReportTotal(PageType.ACCRUED_PREPAID, zero, identities, blank=True)
            total = a[-1]
            if items:
                _settle(
                    identities,
                    f"{which} invoices sum to section total",
                    sum((v.amount for v in items), Decimal(0)),
                    total.amount,
                    [*items, total],
                    page.number,
                )
            return ReportTotal(PageType.ACCRUED_PREPAID, total, identities, rows=len(items))
        if "invoices" in ln.key:
            break  # ran into the other section without finding a total
        items.extend(_amounts_on(ln, page, ln.text))
    return ReportTotal(PageType.ACCRUED_PREPAID, None, identities)


def parse_insurance_schedule(page: Page) -> ReportTotal:
    identities: list[Identity] = []
    lines = page.lines
    start = next((i for i, ln in enumerate(lines) if "policydescription" in ln.key), None)
    totals_idx = next((i for i, ln in enumerate(lines) if ln.key.startswith("totals")), None)
    if totals_idx is None:
        return ReportTotal(PageType.INSURANCE_SCHEDULE, None, identities, whole_dollars=True)
    ln = lines[totals_idx]
    nums = parse_whole_amounts(ln.text)
    if not nums:
        return ReportTotal(PageType.INSURANCE_SCHEDULE, None, identities, whole_dollars=True)
    total = Value(nums[-1], page.number, ln.bbox, "Insurance schedule — prepaid balance")

    row_vals: list[Value] = []
    for row in lines[(start + 1 if start is not None else 0) : totals_idx]:
        last = row.words[-1].text
        if last in {"-", "–", "—"}:
            row_vals.append(Value(Decimal(0), page.number, row.bbox, row.text))
        elif re.fullmatch(r"\d{1,3}(?:,\d{3})*", last):
            row_vals.append(Value(Decimal(last.replace(",", "")), page.number, row.bbox, row.text))
    if row_vals:
        _settle(
            identities,
            "policy prepaid balances sum to TOTALS",
            sum((v.amount for v in row_vals), Decimal(0)),
            total.amount,
            [total],
            page.number,
        )
    return ReportTotal(
        PageType.INSURANCE_SCHEDULE, total, identities, whole_dollars=True, rows=len(row_vals)
    )


def parse_reserve_schedule(page: Page) -> ReportTotal:
    identities: list[Identity] = []
    for ln in page.lines:
        if squash(re.split(r"[\d(]", ln.text, maxsplit=1)[0]) == "total":
            a = _amounts_on(ln, page, "Reserve schedule — ending balance")
            if not a:
                continue
            if len(a) == 5:
                start, receipts, adj, expenses, balance = a
                _settle(
                    identities,
                    "start + receipts + adjustments - expenses = balance",
                    start.amount + receipts.amount + adj.amount - expenses.amount,
                    balance.amount,
                    a,
                    page.number,
                )
            return ReportTotal(PageType.RESERVE_SCHEDULE, a[-1], identities)
    return ReportTotal(PageType.RESERVE_SCHEDULE, None, identities)


# --------------------------------------------------------------------------
# Packet
# --------------------------------------------------------------------------


@dataclass
class Packet:
    page_types: dict[int, PageType]
    balance_sheet: BalanceSheet | None
    income_expense: dict[str, IncomeExpense]
    bank_recs: list[BankRec]
    ar_aging: ReportTotal | None
    prepaid_assessments: ReportTotal | None
    accrued: ReportTotal | None
    prepaid_expenses: ReportTotal | None
    insurance: ReportTotal | None
    reserve_schedule: ReportTotal | None


def extract_packet(pages: list[Page]) -> Packet:
    types = {p.number: classify(p) for p in pages}
    by_type: dict[PageType, list[Page]] = {}
    for p in pages:
        by_type.setdefault(types[p.number], []).append(p)

    def first(t: PageType) -> Page | None:
        return by_type.get(t, [None])[0]

    bs_page = first(PageType.BALANCE_SHEET)
    ie: dict[str, IncomeExpense] = {}
    for dept in ("operating", "reserve"):
        dept_pages = [
            p for p in by_type.get(PageType.INCOME_EXPENSE, []) if _ie_department(p) == dept
        ]
        if dept_pages:
            ie[dept] = parse_income_expense(dept_pages, dept)

    ap = first(PageType.ACCRUED_PREPAID)
    ins = first(PageType.INSURANCE_SCHEDULE)
    rs = first(PageType.RESERVE_SCHEDULE)
    ar_pages = by_type.get(PageType.AR_AGING)
    pp_pages = by_type.get(PageType.PREPAID_ASSESSMENTS)
    return Packet(
        page_types=types,
        balance_sheet=parse_balance_sheet(bs_page) if bs_page else None,
        income_expense=ie,
        bank_recs=[parse_bank_rec(p) for p in by_type.get(PageType.BANK_REC, [])],
        ar_aging=parse_ar_aging(ar_pages) if ar_pages else None,
        prepaid_assessments=parse_prepaid_assessments(pp_pages) if pp_pages else None,
        accrued=parse_accrued_prepaid(ap, "accrued") if ap else None,
        prepaid_expenses=parse_accrued_prepaid(ap, "prepaid") if ap else None,
        insurance=parse_insurance_schedule(ins) if ins else None,
        reserve_schedule=parse_reserve_schedule(rs) if rs else None,
    )
