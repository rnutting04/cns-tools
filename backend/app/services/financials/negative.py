"""Negative bank balances: any deposit account on the balance sheet below zero.

Reads the same deposit rows as the FDIC check (Bank, CD/CDAR's, investment,
money market and cash sections, minus petty cash, receivables and the
like) and flags each one with a negative figure in any column: an overdrawn
operating account usually shows as "(1,234.56)" in Operating and Total.

The figures are OCR'd, and a lost parenthesis turns an overdraft into a
positive balance. So the result also says whether the accounts' Total
column summed to "Total Bank": if it didn't, a sign may have been misread
and the association is flagged for a look even with no negative found.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .extract import BalanceSheet, BSRow, Value
from .fdic import _is_deposit_row
from .pdf import BBox


@dataclass
class BankAccount:
    label: str
    amounts: dict[str, Decimal]  # column -> amount, as read
    value: Value  # the most negative figure (or Total), for page/bbox evidence
    bbox: BBox  # the whole line: name and figures
    negative: bool
    verified: bool | None  # did the line's figures pass the sheet's sums?
    notes: list[str] = field(default_factory=list)

    @property
    def amount(self) -> Decimal:
        return self.value.amount


@dataclass
class NegativeResult:
    accounts: list[BankAccount]  # negative first, then in sheet order
    # Did the bank accounts sum to "Total Bank"? None when there's no such row.
    totals_ok: bool | None
    total_checks: list[str]  # descriptions of the sums that failed
    # When the sum failed: the bank section (page, box), to show the reviewer.
    bank_area: tuple[int, BBox] | None = None

    @property
    def negatives(self) -> list[BankAccount]:
        return [a for a in self.accounts if a.negative]


TOTAL_BANK_CHECK = "bank accounts sum to Total Bank (total)"  # as extract.py words it

_COLUMN_NAMES = {"operating": "Operating", "reserve": "Reserve", "total": "Total"}


def _column(col: str) -> str:
    return _COLUMN_NAMES.get(col, col.replace("fund", "Fund "))  # master assoc. fund columns


def _line_box(row: BSRow) -> BBox:
    box = row.bbox
    for v in row.values.values():
        if abs(v.bbox.cy - row.bbox.cy) <= 6:  # skip a figure drifted from another line
            box = box.union(v.bbox)
    return box


def _overdrawn_note(row: BSRow, below: dict[str, Value]) -> str:
    # Name the department/fund column; Total only when it's the sole figure.
    parts = {c: v for c, v in below.items() if c != "total"} or below
    cols = ", ".join(f"{_column(c)} {v.amount:,.2f}" for c, v in parts.items())
    total = row.values.get("total")
    if total is not None and total.amount >= 0:
        # A master association's shared account: one fund's share is
        # overdrawn though the account as a whole isn't.
        return (
            f"Negative in {cols}, though the account's total is {total.amount:,.2f}: "
            "that column's share of the account is overdrawn."
        )
    return f"Overdrawn: {cols}. Check the bank rec and fund the account."


def _verified(values: list[Value]) -> bool | None:
    states = [v.verified for v in values]
    if any(s is False for s in states):
        return False
    return True if any(s for s in states) else None


def negative_balances(bs: BalanceSheet) -> NegativeResult:
    accounts: list[BankAccount] = []
    for row in bs.rows:
        if row.key == "totalassets":
            break  # assets only
        if not _is_deposit_row(row):
            continue
        amounts = {c: v.amount for c, v in row.values.items()}
        if not any(amounts.values()):
            continue  # zero balance: closed or unused
        below = {c: v for c, v in row.values.items() if v.amount < 0}
        if below:
            value = min(below.values(), key=lambda v: v.amount)
        else:
            value = row.amount("total") or next(iter(row.values.values()))
        acct = BankAccount(
            label=row.label,
            amounts=amounts,
            value=value,
            bbox=_line_box(row),
            negative=bool(below),
            verified=_verified(list(row.values.values())),
        )
        if below:
            acct.notes.append(_overdrawn_note(row, below))
        accounts.append(acct)

    # Only the Total column: a lost parenthesis on any account always breaks
    # it, while the department/fund columns fail for reasons that aren't a
    # sign (a figure OCR dropped, a two-word fund header read as one column).
    checks = [i for i in bs.identities if i.description == TOTAL_BANK_CHECK]
    failed = [i.description for i in checks if not i.ok]
    accounts.sort(key=lambda a: not a.negative)  # stable: sheet order within each group
    result = NegativeResult(accounts, (not failed) if checks else None, failed)
    if failed:
        result.bank_area = _bank_area(bs)
    return result


def _bank_area(bs: BalanceSheet) -> tuple[int, BBox] | None:
    """The "Bank" section from its first account to its Total Bank line."""
    total = next((r for r in bs.rows if r.key.startswith("totalbank")), None)
    if total is None or not total.values:
        return None
    page = next(iter(total.values.values())).page
    rows = [r for r in [*bs.bank_rows, total] if any(v.page == page for v in r.values.values())]
    return page, BBox.union_all([_line_box(r) for r in rows])


__all__ = ["TOTAL_BANK_CHECK", "BankAccount", "NegativeResult", "negative_balances"]
