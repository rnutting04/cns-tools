"""Month-end financial packet checks: OCR geometry, self-verification, rules."""

from decimal import Decimal
from pathlib import Path

import pytest

from app.services.financials import Status, check_packet
from app.services.financials.checks import run_checks
from app.services.financials.extract import (
    PageType,
    _has_word,
    _page_of,
    classify,
    extract_packet,
    parse_ap_aging,
    parse_balance_sheet,
    parse_prepaid_assessments,
)
from app.services.financials.pdf import (
    BBox,
    Page,
    Word,
    estimate_skew,
    group_lines,
    parse_amounts,
)

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


class TestOcrTolerance:
    @pytest.mark.parametrize(
        "word, header, found",
        [
            ("csc", {"cse", "prepaid"}, True),  # one letter wrong
            ("reserve", {"reserves"}, True),  # plural
            ("reserve", {"resexves"}, True),  # plural + one letter wrong
            ("balance", {"balanc"}, True),  # letter dropped
            ("prepaid", {"cscprepaid"}, True),  # run together
            ("reconciliation", {"bankrecoxciliation"}, True),  # run together + typo
            ("ar", {"or"}, False),  # short words must match exactly
            ("sheet", {"street"}, False),  # two edits apart
            ("register", {"registry", "reg"}, False),
        ],
    )
    def test_has_word(self, word, header, found):
        assert _has_word(header, word) is found

    @pytest.mark.parametrize(
        "footer, expected",
        [
            ("11/9/2026 2:34:08 PM Page 2of2", (2, 2)),
            ("Page 2 of 6", (2, 6)),
            ("2/5/2026 10:32:13 AM Page 30f 6", (3, 6)),  # OCR read "of" as "0f"
            ("Page 10 of 12", (10, 12)),
        ],
    )
    def test_page_of_footer(self, footer, expected):
        page = make_page([(700, [(30 + 40 * i, w) for i, w in enumerate(footer.split())])])
        assert _page_of(page) == expected

    def test_untitled_page_continues_the_report_before_it(self):
        def page(n, title):
            rows = [(30, [(30, w) for w in title])] if title else []
            rows.append(
                (45, [(30, "Resident"), (90, "Contact"), (150, "Property"), (210, "Address")])
            )
            rows.append((700, [(30, "Page"), (60, str(n)), (75, "of"), (90, "2")]))
            return make_page(rows, number=n)

        packet = extract_packet([page(1, ["CSC_Prepaid"]), page(2, ["#@!%"])])
        assert packet.page_types == {
            1: PageType.PREPAID_ASSESSMENTS,
            2: PageType.PREPAID_ASSESSMENTS,
        }

    def test_unreadable_balance_sheet_is_review_not_an_error(self):
        page = make_page(
            [(30, [(30, "Balance"), (75, "Sheet")]), (85, [(293, "Assets"), (353, "Equity")])]
        )
        assert classify(page) is PageType.BALANCE_SHEET
        [result] = run_checks(extract_packet([page]))
        assert result.status is Status.REVIEW


class TestClassify:
    def test_balance_sheet_title_split_out_of_order(self):
        # BCC Oct 2026: OCR read "GL Balance Sheet" as "Sheet" above "GL Balance".
        page = make_page(
            [
                (35, [(30, "Sheet"), (300, "Friday,"), (340, "November")]),
                (38.5, [(30, "GL"), (45, "Balance")]),
                (56, [(30, "Period"), (70, "10/31/2026")]),
                (87, [(293, "Operating"), (353, "Reserve"), (413, "Total")]),
            ]
        )
        assert classify(page) is PageType.BALANCE_SHEET

    @pytest.mark.parametrize(
        "header, expected",
        [
            # Title words out of order / on separate lines, plus a column clue.
            (["Reconciliation Expanded", "Bank Summary", "Statement Date"], PageType.BANK_REC),
            (["Report Expense", "and Income", "Actual Budget Variance"], PageType.INCOME_EXPENSE),
            (["Insurance of Schedule", "Policy Description"], PageType.INSURANCE_SCHEDULE),
            (["Schedule", "Reserves", "Code Receipts Expenses"], PageType.RESERVE_SCHEDULE),
            (["Prepaid Invoices", "Accrued", "Vendor Services"], PageType.ACCRUED_PREPAID),
            (["Prepaid Period", "CSC", "Resident Contact"], PageType.PREPAID_ASSESSMENTS),
            (["Register Check", "By Department"], PageType.CHECK_REGISTER),
            # Title words without the clue stay unclassified.
            (["Schedule", "Reserve"], PageType.OTHER),
            (["Income Expense"], PageType.OTHER),
        ],
    )
    def test_title_words_in_any_order(self, header, expected):
        rows = [
            (30 + 15 * i, [(30 + 60 * j, w) for j, w in enumerate(line.split())])
            for i, line in enumerate(header)
        ]
        assert classify(make_page(rows)) is expected

    def test_balance_word_alone_is_not_a_balance_sheet(self):
        page = make_page([(30, [(30, "Statement"), (90, "Balance")]), (45, [(30, "Total")])])
        assert classify(page) is PageType.OTHER


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

    def test_total_with_ocr_punctuation_for_minus_is_read(self):
        # AMC Oct 2026: "-11,030.10" read as "“11,030.10".
        pp = _prepaid_page(["-60.00", "-40.00"], "“100.00")
        total = parse_prepaid_assessments([pp])
        assert total.total.amount == D("100.00")
        assert all(i.ok for i in total.identities)


class TestAPAging:
    def _page(self, grand: str, bank_totals: list[str], assoc: str) -> Page:
        rows = [(30, [(30, "AP"), (50, "DS"), (70, "Aging"), (105, "Detail")])]
        rows.append((45, [(30, "Vendor"), (90, "Date"), (130, "Invoice"), (200, "Current")]))
        y = 70
        for i, t in enumerate(bank_totals):
            rows.append(
                (y, [(30, f"100{i}"), (60, "Oper"), (90, "Truist"), (140, "Totals:"), (300, t)])
            )
            y += 15
        rows.append((y, [(30, "Morton"), (75, "Village"), (115, "Totals:"), (300, assoc)]))
        rows.append((y + 15, [(240, "Total:"), (275, grand)]))
        return make_page(rows, number=14)

    def test_total_ties_to_gl_2010_with_both_identities(self):
        page = self._page("$38,789.77", ["8,156.27", "30,633.50"], "38,789.77")
        assert classify(page) is PageType.AP_AGING
        rep = parse_ap_aging([page])
        assert rep.total.amount == D("38789.77")
        assert [i.ok for i in rep.identities] == [True, True]

    def test_total_that_disagrees_with_its_buckets_is_unverified(self):
        rep = parse_ap_aging([self._page("$5,688.72", ["5,588.72"], "5,588.72")])
        assert rep.total.verified is False

    def test_absent_report_is_not_applicable(self):
        results = {r.id: r for r in run_checks(extract_packet([_balance_sheet()]))}
        assert results["accounts_payable"].status is Status.NOT_APPLICABLE


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


_IE_COLS = (200, 250, 300, 350, 400, 450, 500)  # YTD actual is the 4th column


def _ie_page(rows: list[tuple[list[str], list[str | None]]], number: int = 2) -> Page:
    """Operating I&E page. Each row is (label words, 7 amounts); None drops
    that amount, as when OCR loses a figure."""
    out = [
        (30, [(30, "Operating"), (90, "Income"), (130, "and"), (155, "Expense")]),
        (45, [(200, "Current"), (240, "Month"), (350, "Year"), (375, "To"), (390, "Date")]),
    ]
    for i, (label, amounts) in enumerate(rows):
        cells = [(30 + 45 * j, w) for j, w in enumerate(label)]
        cells += [(x, a) for x, a in zip(_IE_COLS, amounts, strict=True) if a is not None]
        out.append((70 + 15 * i, cells))
    return make_page(out, number=number)


_REV = (["TOTAL", "REVENUES"], ["10.00", "9.00", "1.00", "100.00", "90.00", "10.00", "120.00"])
_EXP = (["TOTAL", "EXPENSES"], ["6.00", "5.00", "(1.00)", "60.00", "50.00", "(10.00)", "80.00"])


class TestDeskew:
    def test_tilted_rows_regroup_onto_their_labels(self):
        # Rows rise 0.013pt per pt to the right, as on CAR's I&E page.
        slope = -0.013
        words = []
        for i, (label, amounts) in enumerate([_REV, _EXP, _REV, _EXP]):
            top = 100 + 15 * i
            for j, w in enumerate(label):
                x = 30 + 45 * j
                words.append(Word(w, BBox(x, top + slope * x, x + 40, top + 9 + slope * x)))
            for x, a in zip(_IE_COLS, amounts, strict=True):
                words.append(Word(a, BBox(x, top + slope * x, x + 40, top + 9 + slope * x)))
        skew = estimate_skew(group_lines(words))
        assert abs(skew - slope) < 0.001
        lines = group_lines(words, skew=skew)
        assert [len(parse_amounts(ln.text)) for ln in lines] == [7, 7, 7, 7]


class TestIncomeExpenseFallback:
    def _ie(self, rows):
        return extract_packet([_balance_sheet(), _ie_page(rows)]).income_expense["operating"]

    def test_excess_line_missing_a_figure_is_read_by_column(self):
        excess = (["EXCESS", "REVENUE"], ["4.00", "4.00", None, "40.00", "40.00", "0.00", "40.00"])
        net = self._ie([_REV, _EXP, excess]).ytd_net
        assert net.amount == D("40.00")
        assert net.guessed
        assert net.verified is True  # revenues - expenses confirms the guess

    def test_unconfirmed_guess_that_matches_still_needs_review(self):
        # Balance sheet operating net income is (1.00); no totals to confirm the guess.
        dues = (["Assessments"], ["1.00", "1.00", "0.00", "9.00", "9.00", "0.00", "12.00"])
        excess = (["EXCESS", "REVENUE"], [None, "1.00", "0.00", "(1.00)", "0.00", "(1.00)", None])
        packet = extract_packet([_balance_sheet(), _ie_page([dues, excess])])
        r = next(r for r in run_checks(packet) if r.id == "net_income:operating")
        assert r.right.amount == D("-1.00")
        assert r.right.guessed
        assert r.status is Status.REVIEW

    def test_unreadable_figure_still_points_at_its_line(self):
        packet = extract_packet([_balance_sheet(), _ie_page([(["EXCESS", "REVENUE"], [None] * 7)])])
        r = next(r for r in run_checks(packet) if r.id == "net_income:operating")
        assert r.status is Status.REVIEW
        assert r.right.amount is None
        assert r.right.page == 2 and r.right.bbox is not None


# --------------------------------------------------------------------------
# Real packets (not committed — they contain owner names and balances)
# --------------------------------------------------------------------------

TEST_DATA = Path(__file__).resolve().parents[2] / "test_data"

EXPECTED = {
    # Page 4 (operating I&E) is scanned ~0.75° off level: the right-hand
    # figures sit up to 7pt above their labels until the page is deskewed.
    "CAR October 2026.pdf": {
        "bank:1702": Status.PASS,
        "bank_rec_zero:1702": Status.PASS,
        "bank:1745": Status.PASS,
        "bank_rec_zero:1745": Status.PASS,
        "bank:8621": Status.PASS,
        "bank:8272": Status.PASS,
        "ar": Status.PASS,
        "prepaid_expenses": Status.PASS,
        "prepaid_assessments": Status.PASS,
        "prepaid_insurance": Status.PASS,  # 4,011.00 vs whole-dollar 4,010
        "accrued_expenses": Status.PASS,
        "accounts_payable": Status.NOT_APPLICABLE,
        # Titled "Reserves Schedule"; ties to reserve assets less reserve
        # liabilities (279,126.07 - 1,895.00 = 277,231.07).
        "reserve_schedule": Status.PASS,
        "net_income:operating": Status.PASS,
        "net_income:reserve": Status.PASS,
    },
    # Titled "GL Balance Sheet". Reserve AP of 30,633.50 sits between reserve
    # assets and the reserve schedule balance.
    "BCC September 2026.pdf": {
        "bank:5711": Status.PASS,
        "bank_rec_zero:5711": Status.PASS,
        "bank:5738": Status.PASS,
        "bank_rec_zero:5738": Status.PASS,
        "bank:711": Status.PASS,
        "bank_rec_zero:711": Status.PASS,
        "ar": Status.PASS,
        "prepaid_expenses": Status.PASS,
        "prepaid_assessments": Status.PASS,
        "prepaid_insurance": Status.PASS,
        "accrued_expenses": Status.PASS,
        "accounts_payable": Status.PASS,
        "reserve_schedule": Status.PASS,
        "net_income:operating": Status.PASS,
        "net_income:reserve": Status.PASS,
    },
    # OCR put "Sheet" on the line above "GL Balance" in the title.
    "BCC October 2026.pdf": {
        "bank:5711": Status.PASS,
        "bank_rec_zero:5711": Status.PASS,
        "bank:5738": Status.PASS,
        "bank_rec_zero:5738": Status.PASS,
        "bank:711": Status.PASS,
        "bank_rec_zero:711": Status.PASS,
        "ar": Status.PASS,
        "prepaid_expenses": Status.PASS,
        "prepaid_assessments": Status.PASS,
        "prepaid_insurance": Status.PASS,
        "accrued_expenses": Status.PASS,
        "accounts_payable": Status.PASS,
        "reserve_schedule": Status.PASS,
        "net_income:operating": Status.PASS,
        "net_income:reserve": Status.PASS,
    },
    # Balance sheet runs over 2 pages (Net Income on page 2); the 8458 rec
    # summary spills onto a second page; "Bank Ozk - 1435 (.50%)" has a note
    # after the account number. No 1527 rec and no reserve schedule in the packet.
    "FAI October 2026.pdf": {
        "bank:8458": Status.PASS,
        "bank_rec_zero:8458": Status.PASS,
        "bank:3950": Status.PASS,
        "bank_rec_zero:3950": Status.PASS,
        "bank:1527": Status.MISSING,
        "bank:1435": Status.PASS,
        "bank_rec_zero:1435": Status.PASS,
        "ar": Status.PASS,
        "prepaid_expenses": Status.NOT_APPLICABLE,
        "prepaid_assessments": Status.PASS,
        "prepaid_insurance": Status.PASS,
        "accrued_expenses": Status.PASS,
        "accounts_payable": Status.NOT_APPLICABLE,
        "reserve_schedule": Status.MISSING,
        "net_income:operating": Status.PASS,
        "net_income:reserve": Status.PASS,
    },
    # Prepaid assessment total OCR'd as "“11,030.10" (minus sign read as a quote).
    "AMC October 2026.pdf": {
        "bank:9298": Status.PASS,
        "bank_rec_zero:9298": Status.PASS,
        "bank:9301": Status.PASS,
        "bank_rec_zero:9301": Status.PASS,
        "bank:1715": Status.PASS,
        "bank_rec_zero:1715": Status.PASS,
        "ar": Status.PASS,
        "prepaid_expenses": Status.NOT_APPLICABLE,
        "prepaid_assessments": Status.PASS,
        "prepaid_insurance": Status.PASS,
        "accrued_expenses": Status.PASS,
        "accounts_payable": Status.NOT_APPLICABLE,
        "reserve_schedule": Status.PASS,
        "net_income:operating": Status.PASS,
        "net_income:reserve": Status.PASS,
    },
    # Year end: has the AP DS Aging Detail (Total 5,588.72 = GL 2010). Page 2
    # of CSC_Prepaid is titled "CSE Prepaid" in OCR. Prepaid insurance is a
    # real 1.84 difference: 193,667.84 vs a whole-dollar schedule of 193,666
    # over 2 policies (rounding allows at most 1.00).
    "MOR December 2025.pdf": {
        "bank:2752": Status.PASS,
        "bank_rec_zero:2752": Status.PASS,
        "bank:2760": Status.PASS,
        "bank_rec_zero:2760": Status.PASS,
        "ar": Status.PASS,
        "prepaid_expenses": Status.NOT_APPLICABLE,
        "prepaid_assessments": Status.PASS,
        "prepaid_insurance": Status.FAIL,
        "accrued_expenses": Status.PASS,
        "accounts_payable": Status.PASS,
        "reserve_schedule": Status.PASS,
        "net_income:operating": Status.PASS,
        "net_income:reserve": Status.PASS,
    },
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
    path = next(
        (p for p in (TEST_DATA / name, TEST_DATA / "context" / name) if p.exists()),
        TEST_DATA / name,
    )
    if not path.exists():
        pytest.skip(f"{name} not present")
    _, results = check_packet(path)
    got = {r.id: r.status for r in results}
    assert {k: got.get(k) for k in EXPECTED[name]} == EXPECTED[name]
    # No mismatches beyond the real ones listed above.
    expected_fails = {k for k, v in EXPECTED[name].items() if v is Status.FAIL}
    assert not [r.id for r in results if r.status is Status.FAIL and r.id not in expected_fails]
