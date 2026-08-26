"""Cross-check: reclassification between taxonomies must pass; real losses must fail."""

import pytest

from app.services.budget.exceptions import CrossCheckFailed
from app.services.budget.schema import BudgetSection, IngestedLine, IngestResult
from app.services.budget.stages import cross_check

pytestmark = pytest.mark.unit


def _ingest(lines: list[tuple[BudgetSection, str, float]], pdf_totals: dict) -> IngestResult:
    return IngestResult(
        months_elapsed=6,
        lines=[
            IngestedLine(label=label, section=section, ytd_actual=amount)
            for section, label, amount in lines
        ],
        pdf_section_totals=pdf_totals,
    )


class TestExpenseReclassification:
    def test_section_disagreement_that_nets_out_is_not_a_failure(self):
        """Reproduces a real run: the workbook files "Annual Corporate Report"
        ($61.25) and "Pool/Spa Permit" ($250.00) under OTHER, while the report
        counts them under ADMINISTRATION and MAINTENANCE. Same dollars, three
        section mismatches, and it used to fail the whole job."""
        ingest = _ingest(
            [
                (BudgetSection.ADMINISTRATION, "Management Fees", 5105.50),
                (BudgetSection.MAINTENANCE, "Ground Maint.", 48198.05),
                (BudgetSection.OTHER, "Insurance", 6106.36),
                (BudgetSection.OTHER, "Annual Corporate Report", 61.25),
                (BudgetSection.OTHER, "Pool/Spa Permit", 250.00),
            ],
            {
                "ADMINISTRATION": 5166.75,  # includes the $61.25
                "MAINTENANCE": 48448.63,  # includes the $250.58
                "OTHER": 6157.61,
            },
        )
        cross_check.run(ingest)  # must not raise

        notes = " ".join(ingest.missing_data)
        assert "Section heading note" in notes
        assert "no amount is missing" in notes

    def test_a_genuinely_missing_line_still_fails(self):
        """A dropped line does not net out across sections, so it must still halt."""
        ingest = _ingest(
            [
                (BudgetSection.ADMINISTRATION, "Management Fees", 5105.50),
                (BudgetSection.MAINTENANCE, "Ground Maint.", 20000.00),
            ],
            {"ADMINISTRATION": 5105.50, "MAINTENANCE": 48448.63},
        )
        with pytest.raises(CrossCheckFailed) as exc:
            cross_check.run(ingest)
        assert any("EXPENSES" in m for m in exc.value.mismatches)

    def test_exact_match_produces_no_notes(self):
        ingest = _ingest(
            [
                (BudgetSection.ADMINISTRATION, "Management Fees", 5105.50),
                (BudgetSection.MAINTENANCE, "Ground Maint.", 48448.63),
            ],
            {"ADMINISTRATION": 5105.50, "MAINTENANCE": 48448.63},
        )
        cross_check.run(ingest)
        assert ingest.missing_data == []

    def test_no_pdf_totals_is_a_no_op(self):
        ingest = _ingest([(BudgetSection.ADMINISTRATION, "CPA", 100.0)], {})
        cross_check.run(ingest)
        assert ingest.missing_data == []


class TestPrintedGrandTotals:
    def test_report_grouping_differs_from_workbook_but_totals_agree(self):
        """GOR's report files Insurance ($232,862.56), income taxes and bad debts
        under "Administrative"; its workbook files them under OTHER. Reconciling
        per section made that look like $203k missing from ADMINISTRATION."""
        ingest = _ingest(
            [
                (BudgetSection.ADMINISTRATION, "Management Fees", 84466.50),
                (BudgetSection.MAINTENANCE, "Ground Maint.", 147679.87),
                (BudgetSection.OTHER, "Insurance", 232862.56),
                (BudgetSection.OTHER, "Income Taxes", 9054.34),
                (BudgetSection.UTILITIES, "Electricity", 220106.98),
            ],
            {"ADMINISTRATION": 287501.93, "MAINTENANCE": 212091.48},
        )
        ingest.pdf_total_expenses = 694170.25
        cross_check.run(ingest)  # totals agree; must not raise

        notes = " ".join(ingest.missing_data)
        assert "Section heading note" in notes
        assert "no amount is missing" in notes

    def test_printed_total_still_catches_a_real_miss(self):
        ingest = _ingest(
            [(BudgetSection.ADMINISTRATION, "Management Fees", 84466.50)],
            {},
        )
        ingest.pdf_total_expenses = 694170.25
        with pytest.raises(CrossCheckFailed) as exc:
            cross_check.run(ingest)
        assert any("TOTAL EXPENSES" in m for m in exc.value.mismatches)

    def test_printed_revenue_total_is_preferred_over_subtotals(self):
        """The report prints TOTAL REVENUES 689,047.17; trust it over summing."""
        ingest = _ingest(
            [(BudgetSection.REVENUE_OPERATING, "Assessments", 689047.17)],
            {"REVENUE_OPERATING": 1.0},  # a bogus/synthesised subtotal
        )
        ingest.pdf_total_revenue = 689047.17
        cross_check.run(ingest)  # must not raise


class TestReserveFundScope:
    def test_report_totalling_only_the_operating_fund_reconciles(self):
        """MCP's report prints TOTAL REVENUES $82,262.08 for the operating fund,
        while the workbook also carries $19,808.78 of reserve revenue on a
        separate statement. That is not a missing $19.8k."""
        ingest = _ingest(
            [
                (BudgetSection.REVENUE_OPERATING, "Member Assessments", 80738.50),
                (BudgetSection.REVENUE_OPERATING, "Other Income", 1523.58),
                (BudgetSection.REVENUE_RESERVES, "Assessments", 19801.50),
                (BudgetSection.REVENUE_RESERVES, "Interest", 7.28),
            ],
            {},
        )
        ingest.pdf_total_revenue = 82262.08
        cross_check.run(ingest)  # must not raise

        notes = " ".join(ingest.missing_data)
        assert "operating fund only" in notes
        assert "19,808.78" in notes

    def test_report_including_reserves_also_reconciles(self):
        """The other convention must keep working."""
        ingest = _ingest(
            [
                (BudgetSection.REVENUE_OPERATING, "Member Assessments", 80738.50),
                (BudgetSection.REVENUE_RESERVES, "Assessments", 19801.50),
            ],
            {},
        )
        ingest.pdf_total_revenue = 100540.00
        cross_check.run(ingest)
        assert not any("operating fund only" in n for n in ingest.missing_data)

    def test_a_real_shortfall_still_fails_under_either_reading(self):
        ingest = _ingest(
            [
                (BudgetSection.REVENUE_OPERATING, "Other Income", 1523.58),
                (BudgetSection.REVENUE_RESERVES, "Assessments", 19801.50),
            ],
            {},
        )
        ingest.pdf_total_revenue = 82262.08  # the $80,738.50 assessments line is gone
        with pytest.raises(CrossCheckFailed):
            cross_check.run(ingest)


class TestRevenueUnchanged:
    def test_large_revenue_shortfall_still_fails(self):
        """The revenue path is untouched: a whole missing assessments line halts."""
        ingest = _ingest(
            [(BudgetSection.REVENUE_OPERATING, "Other Income", 15837.15)],
            {"REVENUE_OPERATING": 689047.17},
        )
        with pytest.raises(CrossCheckFailed) as exc:
            cross_check.run(ingest)
        assert any("REVENUE" in m for m in exc.value.mismatches)
