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

from .pdf import (
    BBox,
    Line,
    Page,
    Word,
    group_lines,
    parse_amounts,
    parse_whole_amounts,
    squash,
)

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
    # "Reserve Schedule" or "Reserves Schedule" depending on the association.
    if re.search(r"reserves?schedule", h):
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
    # Read by position because the line didn't parse cleanly. Shown to the
    # reviewer as a best guess; never the basis for a hard "fail" on its own.
    guessed: bool = False


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


def _amount_tokens(words: list[Word]) -> list[tuple[Decimal, BBox]]:
    """Each amount with its own box. A fused token ("7,855.597,499.70") is
    split into per-amount boxes by character position."""
    out: list[tuple[Decimal, BBox]] = []
    for w in words:
        amounts = parse_amounts(w.text)
        if not amounts:
            continue
        if len(amounts) == 1:
            out.append((amounts[0], w.bbox))
            continue
        step = (w.bbox.x1 - w.bbox.x0) / len(amounts)
        for i, a in enumerate(amounts):
            x0 = w.bbox.x0 + i * step
            out.append((a, BBox(x0, w.bbox.top, x0 + step, w.bbox.bottom)))
    return out


def _label_box(line: Line) -> BBox:
    """The box of the line's leading non-numeric words (its label)."""
    label = [w for w in line.words if not re.search(r"\d", w.text)]
    return BBox.union_all([w.bbox for w in label]) if label else line.bbox


def _nearby_amount(
    page: Page,
    line: Line,
    label: str,
    note: str,
    column_x: float | None = None,
    max_dy: float = 9.0,
    rightmost: bool = False,
) -> Value | None:
    """Best-guess amount for a label whose line didn't parse cleanly.

    Looks at amounts on the page within ``max_dy`` points of the label's row
    (OCR often drifts a figure onto a neighbouring line) and to its right.
    With ``column_x``, takes the amount nearest that column; otherwise the
    first (or with ``rightmost``, the last) amount on the nearest row.
    """
    anchor = _label_box(line)
    ay = page.level(anchor)

    def dy(b: BBox) -> float:
        return abs(page.level(b) - ay)

    cands = [
        (a, b) for a, b in _amount_tokens(page.words) if dy(b) <= max_dy and b.x0 >= anchor.x1 - 2
    ]
    if column_x is not None:
        cands = [(a, b) for a, b in cands if abs(b.cx - column_x) <= 45]
        # Nearest row first: the next row's figures can be within max_dy
        # too, and both sit in the same column.
        key = lambda c: (dy(c[1]), abs(c[1].cx - column_x))  # noqa: E731
    else:
        # Keep only the row nearest the label, then take its first/last figure.
        if cands:
            nearest = min(dy(b) for _, b in cands)
            cands = [(a, b) for a, b in cands if dy(b) <= nearest + 3]
        sign = -1 if rightmost else 1
        key = lambda c: (sign * c[1].x0, dy(c[1]))  # noqa: E731
    if not cands:
        return None
    amount, box = min(cands, key=key)
    return Value(amount, page.number, anchor.union(box), label, note=note, guessed=True)


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

    label_lines = group_lines([w for w in body if w.bbox.x1 < label_limit], skew=page.skew)
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
            y = page.level(box)
            row = min(rows, key=lambda r: abs(page.level(r.bbox) - y))
            if abs(page.level(row.bbox) - y) > 14:
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
    # Where the figure should be, when it couldn't be read at all.
    searched: tuple[int, BBox] | None = None


def _ie_label(line: Line) -> str:
    return squash(re.split(r"[\d(]", line.text, maxsplit=1)[0])


def _ytd_column_x(pages: list[Page]) -> float | None:
    """x-centre of the YTD Actual column, from the rows that parsed cleanly."""
    xs = sorted(
        toks[3][1].cx
        for page in pages
        for ln in page.lines
        if len(toks := _amount_tokens(ln.words)) == 7
    )
    return xs[len(xs) // 2] if xs else None


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
    # Label lines seen, parsed cleanly or not, for the positional fallback.
    seen: dict[str, tuple[Page, Line]] = {}
    for page in pages:
        for ln in page.lines:
            label = _ie_label(ln)
            if label.startswith("excessrevenue"):
                kind = "excess"
            elif label in ("totalrevenues", "revenues"):
                kind = "revenue"
            elif label in ("totalexpenses", "expenses"):
                kind = "expense"
            else:
                continue
            seen[kind] = (page, ln)
            amounts = _amounts_on(ln, page, ln.text)
            if len(amounts) != 7:
                continue
            if kind == "excess":
                excess = (page, amounts)
            elif kind == "revenue":
                revenue = (page, amounts)
            else:
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

    # Fallback: a line was found but didn't split into 7 clean amounts
    # (dropped digit, garbled token, figure drifted onto the next OCR line).
    # Read the YTD Actual column by position and flag it as a best guess.
    col = _ytd_column_x(pages)

    def guess(kind: str, label: str, note: str) -> Value | None:
        if kind not in seen or col is None:
            return None
        page, ln = seen[kind]
        return _nearby_amount(page, ln, label, note, column_x=col)

    if "excess" in seen:
        g = guess(
            "excess",
            f"{department.title()} YTD Excess Revenue / Expense",
            "Excess Revenue/Expense line didn't read cleanly; "
            "the Year-to-Date Actual figure was picked by its column position.",
        )
        if g:
            # Confirm the guess the same way as a clean read. A tilted scan
            # usually breaks the totals lines too, so guess those as well.
            r = revenue[1][3] if revenue else guess("revenue", "YTD total revenues", "")
            e = expense[1][3] if expense else guess("expense", "YTD total expenses", "")
            if r and e:
                _settle(
                    identities,
                    f"{department}: YTD revenues - expenses = excess",
                    r.amount - e.amount,
                    g.amount,
                    [r, e, g],
                    g.page,
                )
            return IncomeExpense(department, page_nums, g, identities)

    r = revenue[1][3] if revenue else guess("revenue", "YTD total revenues", "")
    e = expense[1][3] if expense else guess("expense", "YTD total expenses", "")
    if r and e:
        # Excess line missing (MOR's operating I&E ends at TOTAL EXPENSES).
        if r.verified is False or e.verified is False:
            verified = False
        else:
            verified = True if (r.verified and e.verified) else None
        guessed = r.guessed or e.guessed
        note = "Excess Revenue/Expense line not found; derived from YTD totals"
        if guessed:
            note += " (picked by column position — confirm against the report)"
        net = Value(
            r.amount - e.amount,
            e.page,
            e.bbox if r.page != e.page else r.bbox.union(e.bbox),
            f"{department.title()} YTD revenues − expenses",
            verified=verified,
            note=note,
            guessed=guessed,
        )
        return IncomeExpense(department, page_nums, net, identities, derived=True)

    # Nothing readable: point the reviewer at where the figure should be.
    for kind in ("excess", "expense", "revenue"):
        if kind in seen:
            page, ln = seen[kind]
            return IncomeExpense(
                department, page_nums, None, identities, searched=(page.number, ln.bbox)
            )
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
    fallback: tuple[Line, str] | None = None
    for ln in lines:
        text = _GL_FIX.sub("GL", ln.text)
        m = rx.search(text)
        if m:
            amounts = parse_amounts(text[m.end() :])
            if amounts:
                return Value(amounts[0], page.number, ln.bbox, m.group().strip(" :"))
            fallback = fallback or (ln, m.group().strip(" :"))
    if fallback:
        # Label found but its amount drifted off the line in OCR.
        ln, label = fallback
        return _nearby_amount(
            page, ln, label, f"No amount on the {label} line; took the nearest one beside it."
        )
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
    # Where the total should be, when it couldn't be read at all.
    searched: tuple[int, BBox] | None = None


def parse_ar_aging(pages: list[Page]) -> ReportTotal:
    identities: list[Identity] = []
    unread: tuple[Page, Line] | None = None
    for page in reversed(pages):
        for ln in page.lines:
            if ln.key.startswith("count"):
                a = _amounts_on(ln, page, "AR aging total")
                if not a:
                    unread = unread or (page, ln)
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
    return _guess_total(
        PageType.AR_AGING, unread, identities, "AR aging total", "the Count line's balance"
    )


def _guess_total(
    kind: PageType,
    unread: tuple[Page, Line] | None,
    identities: list[Identity],
    label: str,
    what: str,
) -> ReportTotal:
    """The total line was found but had no readable amount on it: take the
    last figure on the nearest row as a best guess, or failing that, point
    the reviewer at the line."""
    if unread is None:
        return ReportTotal(kind, None, identities)
    page, ln = unread
    note = f"Couldn't read {what} cleanly; took the nearest figure as a best guess."
    g = _nearby_amount(page, ln, label, note, rightmost=True)
    if g:
        return ReportTotal(kind, g, identities)
    return ReportTotal(kind, None, identities, searched=(page.number, ln.bbox))


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
            if not a and items:
                # Invoices are listed, so the total can't really be blank:
                # its figure drifted off the line. Guess it and check it
                # against the invoices.
                g = _nearby_amount(
                    page,
                    ln,
                    f"Accrued/Prepaid — {which} total",
                    f"Couldn't read the {which} total cleanly; took the nearest figure "
                    "as a best guess.",
                    rightmost=True,
                )
                if g:
                    a = [g]
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
        return ReportTotal(
            PageType.INSURANCE_SCHEDULE,
            None,
            identities,
            whole_dollars=True,
            searched=(page.number, ln.bbox),
        )
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
    unread: tuple[Page, Line] | None = None
    for ln in page.lines:
        if squash(re.split(r"[\d(]", ln.text, maxsplit=1)[0]) == "total":
            a = _amounts_on(ln, page, "Reserve schedule — ending balance")
            if not a:
                unread = unread or (page, ln)
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
    return _guess_total(
        PageType.RESERVE_SCHEDULE,
        unread,
        identities,
        "Reserve schedule — ending balance",
        "the TOTAL line's balance",
    )


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
