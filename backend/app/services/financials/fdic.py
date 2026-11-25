"""FDIC exposure: total an association's balances at each bank.

Reads the balance sheet's deposit accounts (Bank, CD/CDAR's, investment
and cash sections) and sums the Total column per institution. A total of
$250,000 or more is flagged.

Institution names come from the account labels ("1000 Oper Truist - 5711",
"1319 R-CD Ozk 9/7/27", "1306 R-CD O2ZK ..."), matched against a list of
known banks with the same OCR tolerance as report titles. Deposit rows that
match no known bank are returned separately so nothing is silently dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

from .extract import BalanceSheet, BSRow, Value, _within_one_edit
from .pdf import squash

FDIC_LIMIT = Decimal("250000")

# Canonical name -> letters-only aliases. Short aliases (< 5 letters) must
# start a word ("OZK8/12/27" -> "ozk"); longer ones may appear anywhere and
# tolerate one OCR letter error.
INSTITUTIONS: dict[str, tuple[str, ...]] = {
    "Truist": ("truist",),
    "Huntington": ("huntington",),
    "Centennial": ("centennial",),
    "Bank OZK": ("ozk",),
    "American Momentum Bank (AMB)": ("amb", "americanmomentum"),
    "Ameris": ("ameris", "amerius"),
    "Merrill Lynch": ("merrill", "merrilllynch"),
    "Charles Schwab": ("schwab",),
    "Fidelity": ("fidelity",),
    "BMO": ("bmo",),
    "Raymond James": ("raymondjames",),
    "Morgan Stanley": ("morganstanley",),
    "Edward Jones": ("edwardjones",),
    "Wells Fargo": ("wellsfargo",),
    "Bank of America": ("bankofamerica", "boa"),
    "Chase": ("chase", "jpmorgan"),
    "Regions": ("regions",),
    "Seacoast": ("seacoast",),
    "Synovus": ("synovus",),
    "PNC": ("pnc",),
    "Valley Bank": ("valleybank", "valleynational"),
    "Pinnacle": ("pinnacle",),
    "First Horizon": ("firsthorizon",),
    "Cadence": ("cadence",),
    "TD Bank": ("tdbank",),
    "Citizens": ("citizens",),
    "ServisFirst": ("servisfirst",),
    "Western Alliance": ("westernalliance", "alliancebank"),
    "CIBC": ("cibc",),
    "Flagstar": ("flagstar",),
    "City National": ("citynational",),
}

# Brokerages: balances are typically securities/brokered CDs (SIPC or
# per-issuing-bank FDIC), so a total over the limit needs a closer look.
BROKERAGES = {
    "Merrill Lynch",
    "Charles Schwab",
    "Fidelity",
    "Raymond James",
    "Morgan Stanley",
    "Edward Jones",
}

# Balance sheet sections that hold deposits.
_DEPOSIT_SECTIONS = ("bank", "cd", "cdar", "investment", "money", "saving", "checking", "cash")
# Rows that are never deposits even inside those sections.
_NOT_DEPOSIT = ("petty", "receivable", "prepaid", "allowance", "accrued", "due")
# Reciprocal-deposit programs that spread funds across many banks.
_NETWORK = ("ics", "cdar", "cdars", "icsweep")


@dataclass
class Account:
    label: str
    amount: Decimal
    value: Value  # for page/bbox evidence
    network: bool  # ICS / CDARS reciprocal deposit


@dataclass
class Institution:
    name: str
    total: Decimal
    accounts: list[Account]
    over_limit: bool
    notes: list[str] = field(default_factory=list)


@dataclass
class FdicResult:
    institutions: list[Institution]  # largest first
    unrecognized: list[Account]  # deposit rows whose bank couldn't be named
    limit: Decimal = FDIC_LIMIT


def _words(label: str) -> list[str]:
    return [w for w in (squash(t) for t in re.split(r"[\s\-/()_.,:]+", label)) if w]


def identify(label: str) -> str | None:
    """The institution an account label names, or None."""
    words = _words(label)
    full = squash(label)
    for name, aliases in INSTITUTIONS.items():
        for alias in aliases:
            if len(alias) < 5:
                if any(w.startswith(alias) for w in words):
                    return name
            elif alias in full or any(len(w) >= 6 and _within_one_edit(alias, w) for w in words):
                return name
    return None


def _is_deposit_row(row: BSRow) -> bool:
    if not row.values or row.key.startswith("total"):
        return False
    if any(k in row.key for k in _NOT_DEPOSIT):
        return False
    return any(s in row.section for s in _DEPOSIT_SECTIONS)


def fdic_exposure(bs: BalanceSheet) -> FdicResult:
    by_bank: dict[str, list[Account]] = {}
    unrecognized: list[Account] = []
    for row in bs.rows:
        if row.key == "totalassets":
            break  # assets only
        name = identify(row.label)
        if not (_is_deposit_row(row) or (name and row.values and not row.key.startswith("total"))):
            continue
        v = row.amount("total")
        if v is None or v.amount == 0:
            continue
        acct = Account(
            row.label, v.amount, v, network=any(w in _NETWORK for w in _words(row.label))
        )
        if name:
            by_bank.setdefault(name, []).append(acct)
        else:
            unrecognized.append(acct)

    institutions: list[Institution] = []
    for name, accounts in by_bank.items():
        total = sum((a.amount for a in accounts), Decimal(0))
        inst = Institution(name, total, accounts, over_limit=total >= FDIC_LIMIT)
        network = sum((a.amount for a in accounts if a.network), Decimal(0))
        if network:
            inst.notes.append(
                f"Includes {network:,.2f} in ICS/CDARS, which places deposits across network "
                "banks for FDIC coverage — that portion may not count toward this bank's limit."
            )
        if name in BROKERAGES:
            inst.notes.append(
                "Brokerage account: holdings may be securities or brokered CDs, insured "
                "differently from bank deposits — confirm what's held."
            )
        institutions.append(inst)
    institutions.sort(key=lambda i: i.total, reverse=True)
    return FdicResult(institutions, unrecognized)
