"""Month-end financial packet checks: OCR geometry, self-verification, rules."""

from decimal import Decimal
from pathlib import Path

import pytest

from app.services.financials import Status, check_packet
from app.services.financials.checks import run_checks
from app.services.financials.extract import (
    PageType,
    classify,
    extract_packet,
    parse_balance_sheet,
    parse_prepaid_assessments,
)
from app.services.financials.pdf import BBox, Page, Word, group_lines, parse_amounts

pytestmark = pytest.mark.unit

D = Decimal


def make_page(rows: list[tuple[float, list[tuple[float, str]]]], number: int = 1) -> Page:
    """Synthetic OCR page: each row is (top, [(x0, text), ...])."""
    words = [
        Word(text, BBox(x0, top, x0 + 5.5 * len(text), top + 9))
        for top, cells in rows
        for x0, text in cells
    ]
    page = Page(number=number, width=612, height=792, words=words)
    page.lines = group_lines(words)
    return page


class TestAmounts:
    def test_fused_tokens_split(self):
        assert parse_amounts("7,855.597,499.70") == [D("7855.59"), D("7499.70")]

    def test_negative_forms(self):
        assert parse_amounts("(1,820.74) -3,739.80 0.05") == [
            D("-1820.74"),
            D("-3739.80"),
            D("0.05"),
        ]

    def test_rates_and_ratios_ignored(self):
        assert parse_amounts("R-CD BMO 11/23/26 9m 2.95% (4108)") == []
        assert parse_amounts("0.22048 1.00000") == []


def _balance_sheet(prepaid_row_offset: float = 0) -> Page:
    """A minimal balance sheet. Amount words can be shifted vertically off
    their label row, as WPK's OCR does."""
    o = prepaid_row_offset
    return make_page(
        [
            (30, [(30, "Balance"), (75, "Sheet")]),
            (85, [(293, "Operating"), (353, "Reserve"), (413, "Total")]),
            (100, [(75, "Bank")]),
            (115, [(65, "1000"), (90, "Oper"), (115, "Truist"), (150, "-0263")]),
            (115, [(290, "8,714.69"), (410, "8,714.69")]),
            (130, [(65, "1300"), (90, "Rese"), (115, "Truist"), (150, "-6045")]),
            (130, [(350, "28,582.52"), (410, "28,582.52")]),
            (
                145,
                [
                    (75, "Total"),
                    (100, "Bank"),
                    (290, "8,714.69"),
                    (350, "28,582.52"),
                    (405, "37,297.21"),
                ],
            ),
            (160, [(75, "Liability")]),
            (175, [(65, "2100"), (90, "Prepaid"), (130, "Member"), (170, "Assessment")]),
            (175 + o, [(290, "100.00"), (410, "100.00")]),
            (
                190,
                [
                    (75, "Total"),
                    (100, "Net"),
                    (120, "Income"),
                    (290, "(1.00)"),
                    (350, "2.00"),
                    (410, "1.00"),
                ],
            ),
        ]
    )


class TestBalanceSheetGeometry:
    def test_values_placed_by_column_header(self):
        bs = parse_balance_sheet(_balance_sheet())
        rese = bs.find("1300")
        assert "operating" not in rese.values
        assert rese.values["reserve"].amount == D("28582.52")
        assert all(i.ok for i in bs.identities)

    def test_value_drifted_off_its_row_still_lands_on_it(self):
        bs = parse_balance_sheet(_balance_sheet(prepaid_row_offset=6))
        assert bs.find("2100").amount().amount == D("100.00")

    def test_bank_total_identity_verifies_rows(self):
        bs = parse_balance_sheet(_balance_sheet())
        assert [r.code for r in bs.bank_rows] == ["1000", "1300"]
        assert all(r.amount().verified for r in bs.bank_rows)


def _prepaid_page(row_amounts: list[str], total: str) -> Page:
    rows = [(30, [(30, "CSC_Prepaid"), (120, "Period")])]
    for i, amt in enumerate(row_amounts):
        rows.append(
            (60 + 12 * i, [(30, f"Owner{i},"), (90, "Name"), (300, f"{10800 + i}"), (360, amt)])
        )
    rows.append((60 + 12 * len(row_amounts) + 20, [(360, total)]))
    return make_page(rows)


class TestReviewRouting:
    def _run(self, report_rows: list[str], report_total: str, gl: str = "100.00"):
        bs_page = _balance_sheet()
        # rewrite the 2100 amount
        for w in bs_page.words:
            if w.text == "100.00":
                w.text = gl
        pp = _prepaid_page(report_rows, report_total)
        pp.number = 2
        packet = extract_packet([bs_page, pp])
        return next(r for r in run_checks(packet) if r.id == "prepaid_assessments")

    def test_agreement_passes(self):
        assert self._run(["-60.00", "-40.00"], "-100.00").status is Status.PASS

    def test_verified_disagreement_fails(self):
        r = self._run(["-150.00", "-50.00"], "-200.00")
        assert r.status is Status.FAIL
        assert r.difference == D("-100.00")

    def test_disagreement_with_broken_report_arithmetic_goes_to_review(self):
        # Rows sum to 150 but the total reads 200: something was misread.
        r = self._run(["-100.00", "-50.00"], "-200.00")
        assert r.status is Status.REVIEW

    def test_ocr_dropped_minus_sign_is_tolerated(self):
        pp = _prepaid_page(["-60.00", "40.00"], "-100.00")
        total = parse_prepaid_assessments([pp])
        assert total.total.amount == D("100.00")
        assert all(i.ok for i in total.identities)


class TestBankMatching:
    def test_rec_matched_on_exact_account_suffix(self):
        bs = _balance_sheet()
        rec = make_page(
            [
                (30, [(30, "Bank"), (75, "Reconciliation"), (160, "Expanded"), (220, "Summary")]),
                (45, [(30, "Bank:"), (60, "Oper"), (90, "Truist"), (125, "-"), (132, "0263")]),
                (70, [(30, "Bank"), (60, "Reconciliation"), (140, "Summary:")]),
                (85, [(30, "G/LBalance:"), (200, "8,714.69")]),
                (100, [(30, "Uncleared"), (90, "Checks,"), (130, "Credits:"), (200, "0.00")]),
                (115, [(30, "Uncleared"), (90, "Deposits,"), (140, "Debits:"), (200, "3,739.80")]),
                (130, [(30, "GILDifference:"), (200, "4,974.89")]),
                (145, [(30, "Statement"), (90, "Balance:"), (200, "4,974.89")]),
                (160, [(30, "G/Land"), (70, "Balance"), (115, "Difference:"), (200, "0.00")]),
            ],
            number=2,
        )
        assert classify(rec) is PageType.BANK_REC
        results = {r.id: r for r in run_checks(extract_packet([bs, rec]))}
        assert results["bank:0263"].status is Status.PASS
        assert results["bank:0263"].right.verified is True
        assert results["bank_rec_zero:0263"].status is Status.PASS
        assert results["bank:6045"].status is Status.MISSING


# --------------------------------------------------------------------------
# Real packets (not committed — they contain owner names and balances)
# --------------------------------------------------------------------------

TEST_DATA = Path(__file__).resolve().parents[2] / "test_data"

EXPECTED = {
    "BLE September 2026.pdf": {
        "bank:0263": Status.PASS,
        "bank_rec_zero:0263": Status.PASS,
        "bank:6045": Status.PASS,
        "bank_rec_zero:6045": Status.PASS,
        "ar": Status.PASS,
        "prepaid_expenses": Status.NOT_APPLICABLE,
        "prepaid_assessments": Status.PASS,
        "prepaid_insurance": Status.NOT_APPLICABLE,  # no 1130, no schedule
        "accrued_expenses": Status.NOT_APPLICABLE,
        "reserve_schedule": Status.MISSING,
        "net_income:operating": Status.PASS,
        "net_income:reserve": Status.PASS,
    },
    "MOR September 2026.pdf": {
        "bank:2752": Status.PASS,
        "bank_rec_zero:2752": Status.PASS,
        "bank:2760": Status.PASS,
        "bank_rec_zero:2760": Status.PASS,
        "ar": Status.PASS,
        "prepaid_expenses": Status.NOT_APPLICABLE,
        "prepaid_assessments": Status.PASS,
        "prepaid_insurance": Status.PASS,
        "accrued_expenses": Status.PASS,
        "reserve_schedule": Status.PASS,
        "net_income:operating": Status.PASS,
        "net_income:reserve": Status.PASS,
    },
    "WPK September 2026.pdf": {
        "bank:5810": Status.PASS,
        "bank:2695": Status.PASS,
        "bank:4473": Status.PASS,
        "bank:6110": Status.PASS,
        "bank:4460": Status.PASS,
        "bank:0697": Status.MISSING,
        "bank:695": Status.MISSING,
        "bank:0397": Status.MISSING,
        "ar": Status.PASS,
        "prepaid_assessments": Status.PASS,
        "prepaid_insurance": Status.PASS,  # 63,183.94 vs whole-dollar 63,185
        "accrued_expenses": Status.PASS,
        "reserve_schedule": Status.MISSING,
        "net_income:operating": Status.PASS,
        "net_income:reserve": Status.PASS,
    },
}


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_real_packet(name):
    path = TEST_DATA / name
    if not path.exists():
        pytest.skip(f"{name} not present")
    _, results = check_packet(path)
    got = {r.id: r.status for r in results}
    assert {k: got.get(k) for k in EXPECTED[name]} == EXPECTED[name]
    assert not [r for r in results if r.status is Status.FAIL]
