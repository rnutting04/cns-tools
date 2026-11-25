"""Standalone accounting tools: revenue threshold (compilation/review/audit)
and FDIC exposure per bank."""

from decimal import Decimal
from pathlib import Path

import pytest

from app.services.financials.extract import BalanceSheet, BSRow, Value, extract_packet
from app.services.financials.fdic import FDIC_LIMIT, fdic_exposure, identify
from app.services.financials.pdf import BBox, load_pages
from app.services.financials.thresholds import ReportTier, tier_for

pytestmark = pytest.mark.unit

D = Decimal


@pytest.mark.parametrize(
    "revenue, tier",
    [
        ("149999.99", ReportTier.NONE),
        ("150000.00", ReportTier.COMPILATION),
        ("299999.99", ReportTier.COMPILATION),
        ("300000.00", ReportTier.REVIEW),
        ("499999.99", ReportTier.REVIEW),
        ("500000.00", ReportTier.AUDIT),
        ("1049290.98", ReportTier.AUDIT),
    ],
)
def test_tier_boundaries(revenue, tier):
    assert tier_for(D(revenue)) is tier


@pytest.mark.parametrize(
    "label, bank",
    [
        ("1000 Oper Truist - 5711", "Truist"),
        ("1002 Oper TruistIns Claim - 1715", "Truist"),
        ("1375 Rese TruistInvestment 4.35%", "Truist"),
        ("1302 Rese Bank Ozk - 1435 (.50%)", "Bank OZK"),
        ("1321 R-CDAR OZK8/12/27 52w 3% (4302)", "Bank OZK"),
        ("1306 R-CD O2ZK 3/7/27 6m4.1% (5941)", "Bank OZK"),  # OCR: Z read as 2Z
        ("1005 Oper Ameris Laundry - 1527", "Ameris"),
        ("1010 Oper Amerius - 1111", "Ameris"),
        ("1335 R-CD BMO 7/12/26 12m 1.25% (9317)", "BMO"),
        ("1003 Oper Fidelity- 8621", "Fidelity"),
        ("1400 Rese Merrill Lynch CD", "Merrill Lynch"),
        ("1401 Rese Schwab MM", "Charles Schwab"),
        ("1004 Oper Huntington - 2222", "Huntington"),
        ("1006 Oper Centennial - 3333", "Centennial"),
        ("1007 Oper AMB - 4444", "American Momentum Bank (AMB)"),
        ("1010 Petty Cash", None),
        ("1300 Rese Truistt - 9301", "Truist"),  # one-letter OCR error
    ],
)
def test_identify_bank(label, bank):
    assert identify(label) == bank


def _row(label: str, section: str, amount: str) -> BSRow:
    r = BSRow(label=label, code=label.split()[0], section=section, bbox=BBox(0, 0, 1, 1))
    r.values["total"] = Value(D(amount), 2, BBox(0, 0, 1, 1), label)
    return r


def test_exposure_sums_per_bank_and_flags_at_limit():
    bs = BalanceSheet(
        2,
        [
            _row("1000 Oper Truist - 1", "bank", "100000.00"),
            _row("1300 Rese Truist - 2", "bank", "150000.00"),
            _row("1002 Oper Truist ICS - 3", "bank", "5000.00"),
            _row("1319 R-CD Ozk 9/7/27", "cdcdars", "249999.99"),
            _row("1320 R-CD Mystery Bank", "cdcdars", "1000.00"),
            _row("1010 Petty Cash", "cash", "200.00"),
            _row("1130 Prepaid Insurance", "otherassets", "9999.00"),
            _row("Total Assets", "otherassets", "1.00"),
            _row("2000 Truist Loan", "liability", "50000.00"),  # below Total Assets
        ],
        [],
    )
    r = fdic_exposure(bs)
    by = {i.name: i for i in r.institutions}
    assert by["Truist"].total == D("255000.00") and by["Truist"].over_limit
    assert "ICS/CDARS" in by["Truist"].notes[0]
    assert by["Bank OZK"].total == D("249999.99") and not by["Bank OZK"].over_limit
    assert [a.label for a in r.unrecognized] == ["1320 R-CD Mystery Bank"]
    assert r.limit == FDIC_LIMIT


CONTEXT = Path(__file__).resolve().parents[2] / "test_data" / "context"


@pytest.mark.skipif(not (CONTEXT / "FAI October 2026.pdf").exists(), reason="sample not present")
def test_real_packet_fdic():
    pk = extract_packet(load_pages(CONTEXT / "FAI October 2026.pdf"))
    by = {i.name: i.total for i in fdic_exposure(pk.balance_sheet).institutions}
    assert by == {
        "Truist": D("860109.75"),
        "Bank OZK": D("597990.33"),
        "Ameris": D("10170.95"),
    }
