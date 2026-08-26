# app/services/budget/stages/cross_check.py
#
# Stage 1.5 — Cross-check
#
# Validates that the extracted line-level YTD actuals sum to the section
# totals printed in the PDF. If they don't match, the extractor missed a line,
# misread a value, or the PDF had a layout it couldn't handle.
#
# This is the primary guard against silent extraction errors. A mismatch
# halts the pipeline with a specific message before any budget is assembled.

from app.services.budget.exceptions import CrossCheckFailed
from app.services.budget.schema import IngestResult

# Noise floor: larger of $10 absolute or 0.1% of section total. Covers accumulated
# rounding across 20+ lines without masking a real missed line (~$200+ minimum).
_TOLERANCE_ABS = 10.00
_TOLERANCE_PCT = 0.001  # 0.1%

# Revenue warning threshold: discrepancies under 1% of combined revenue are downgraded
# from a hard failure to a missing_data warning. CSC PDFs frequently produce small
# revenue deltas ($300-$1 000) due to transfer exclusions or column-reading ambiguity.
# A genuine catastrophic miss (whole section dropped) would be 5-20%+.
_REVENUE_WARN_PCT = 0.01  # 1%

# Expense warning threshold, applied to the COMBINED expense total. Section-level
# disagreements between the workbook's headings and the PDF's are reclassification,
# not loss, and net to zero across the total. A genuinely missed line does not net
# out, so it still breaches this.
_EXPENSE_WARN_PCT = 0.01  # 1%


def _tolerance(section_total: float) -> float:
    return max(_TOLERANCE_ABS, abs(section_total) * _TOLERANCE_PCT)


# Revenue sections are checked as a combined total, not individually. A line
# near the OPERATING / RESERVES boundary (e.g. reserve interest income) is often
# grouped differently across associations. If the combined revenue total reconciles,
# an individual section mismatch is a classification issue — not a missing line.
_REVENUE_SECTIONS = {"REVENUE_OPERATING", "REVENUE_RESERVES"}


def _reconcile_fund_scope(
    printed_total: float,
    including_reserves: float,
    excluding_reserves: float,
    limit: float,
) -> tuple[bool, str, float]:
    """
    Match an extracted sum against a printed total that may or may not include
    the reserve fund.

    An income & expense report covers the OPERATING fund. Some associations roll
    reserve assessments into its printed totals; others keep reserves on a
    separate statement entirely — MCP's report totals $82,262.08 of operating
    revenue while the workbook also carries $19,808.78 of reserve revenue.
    Assuming either convention misreports the other as a $19.8k extraction
    failure, so both readings are tried and the one that reconciles wins.

    Returns (reconciled, which_reading, difference).
    """
    diff_incl = abs(including_reserves - printed_total)
    diff_excl = abs(excluding_reserves - printed_total)
    if diff_incl <= limit:
        return True, "including reserves", diff_incl
    if diff_excl <= limit:
        return True, "excluding reserves", diff_excl
    # Neither works — report against the closer reading.
    if diff_excl < diff_incl:
        return False, "excluding reserves", diff_excl
    return False, "including reserves", diff_incl


def _note_section_drift(ingest: IngestResult, pdf_expense_sections: dict[str, float]) -> None:
    """
    Record, without failing, where the report's section headings disagree with
    the workbook's.

    This is expected and common: one association's report files insurance,
    income taxes and bad debts under "Administrative" while its workbook files
    them under OTHER. The dollars are present and correctly extracted — only the
    heading differs — so this is a note for the reviewer, not an error.
    """
    for section_key, pdf_total in sorted(pdf_expense_sections.items()):
        extracted_sum = sum(
            line.ytd_actual or 0.0 for line in ingest.lines if line.section.value == section_key
        )
        if abs(extracted_sum - pdf_total) > _tolerance(pdf_total):
            ingest.missing_data.append(
                f"Section heading note — {section_key}: workbook lines sum to "
                f"${extracted_sum:,.2f} but the report's subtotal is ${pdf_total:,.2f} "
                f"(difference: ${abs(extracted_sum - pdf_total):,.2f}). Totals reconcile, "
                f"so the report groups one or more of these lines under a different "
                f"heading than the workbook does — no amount is missing."
            )


def run(ingest: IngestResult) -> None:
    """
    Stage 1.5: reconcile line-level YTD actuals against PDF section totals.

    Revenue sections (OPERATING + RESERVES) are validated as a combined total
    because individual items can legitimately fall on the boundary between the
    two sections depending on how a given association's report is formatted.
    If the combined revenue total reconciles, per-section revenue differences
    are recorded as classification warnings rather than hard failures.

    All expense sections are checked individually.

    Raises CrossCheckFailed listing every section that fails reconciliation.
    Skips sections where no PDF total was extracted.
    """
    # Nothing to reconcile against only when the report yielded neither a printed
    # grand total nor any printed subtotal. Checking pdf_section_totals alone
    # would skip validation entirely for a report that prints only grand totals.
    if (
        not ingest.pdf_section_totals
        and ingest.pdf_total_revenue is None
        and ingest.pdf_total_expenses is None
    ):
        return

    mismatches: list[str] = []

    # --- Revenue: check combined total first -----------------------------------
    pdf_revenue_sections = {
        k: v for k, v in ingest.pdf_section_totals.items() if k in _REVENUE_SECTIONS
    }
    if pdf_revenue_sections or ingest.pdf_total_revenue is not None:
        # Prefer the printed "TOTAL REVENUES" line over summing subtotals.
        combined_pdf = (
            ingest.pdf_total_revenue
            if ingest.pdf_total_revenue is not None
            else sum(pdf_revenue_sections.values())
        )
        combined_extracted = sum(
            line.ytd_actual or 0.0
            for line in ingest.lines
            if line.section.value in _REVENUE_SECTIONS
        )
        operating_only = sum(
            line.ytd_actual or 0.0
            for line in ingest.lines
            if line.section.value == "REVENUE_OPERATING"
        )
        warn_limit = abs(combined_pdf) * _REVENUE_WARN_PCT
        reconciled, reading, diff = _reconcile_fund_scope(
            combined_pdf, combined_extracted, operating_only, warn_limit
        )
        if reconciled and reading == "excluding reserves":
            # The report totals the operating fund only; reserves live on a
            # separate statement. Not an error, but worth recording.
            ingest.missing_data.append(
                f"The report's revenue total (${combined_pdf:,.2f}) covers the operating "
                f"fund only — the workbook's reserve revenue of "
                f"${combined_extracted - operating_only:,.2f} is accounted for separately."
            )
            combined_extracted = operating_only

        if not reconciled:
            # > 1% off — likely missed an entire revenue section. Hard failure.
            lines_detail = (
                "; ".join(
                    f"{ln.label}: ${ln.ytd_actual:,.2f}"
                    for ln in ingest.lines
                    if ln.section.value in _REVENUE_SECTIONS and ln.ytd_actual is not None
                )
                or "none"
            )
            mismatches.append(
                f"REVENUE (OPERATING + RESERVES combined): extracted lines sum to "
                f"${combined_extracted:,.2f} but PDF shows ${combined_pdf:,.2f} "
                f"(difference: ${diff:,.2f}) — "
                f"extraction likely missed a revenue line or misread a value. "
                f"Extracted revenue lines: {lines_detail}"
            )
        elif diff > _tolerance(combined_pdf):
            # Between noise floor and 1% — typical transfer/column ambiguity. Warn only.
            pct = diff / combined_pdf * 100 if combined_pdf else 0
            ingest.missing_data.append(
                f"Revenue cross-check note ({pct:.2f}% difference): extracted lines "
                f"sum to ${combined_extracted:,.2f} but PDF shows ${combined_pdf:,.2f} "
                f"(${diff:,.2f} off). Review revenue lines — a value may have been "
                f"read from the wrong column, or a small transfer was not fully excluded."
            )

        if reconciled:
            # Revenue is close enough — check per-section classification drift.
            for section_key, pdf_total in pdf_revenue_sections.items():
                extracted_sum = sum(
                    line.ytd_actual or 0.0
                    for line in ingest.lines
                    if line.section.value == section_key
                )
                if abs(extracted_sum - pdf_total) > _tolerance(pdf_total):
                    ingest.missing_data.append(
                        f"Section classification note — {section_key}: lines sum to "
                        f"${extracted_sum:,.2f} but PDF subtotal is ${pdf_total:,.2f} "
                        f"(difference: ${abs(extracted_sum - pdf_total):,.2f}). "
                        f"Total revenue is correct; a line near the OPERATING/RESERVES "
                        f"boundary may be classified in the wrong section. Review and "
                        f"adjust if needed."
                    )

    # --- Expenses: check the combined total, not each section -----------------
    # Sections are assigned from the association's WORKBOOK, while
    # pdf_section_totals come from the headings printed in the PDF. Those are two
    # different taxonomies and they routinely disagree about individual lines —
    # one association's workbook files "Annual Corporate Report" ($61.25) and
    # "Pool/Spa Permit" ($250.00) under OTHER while its report counts them under
    # ADMINISTRATION and MAINTENANCE. Checked per section that reads as three
    # separate failures; checked in total the same dollars reconcile exactly.
    #
    # So the combined total is the hard gate — it still catches a genuinely
    # missed or misread line, which changes the total — and per-section
    # differences are recorded as classification notes for the reviewer.
    pdf_expense_sections = {
        k: v for k, v in ingest.pdf_section_totals.items() if k not in _REVENUE_SECTIONS
    }
    if ingest.pdf_total_expenses is not None:
        # Preferred: the report's own printed TOTAL EXPENSES. Summing per-section
        # subtotals is unreliable — a report may print no subtotal for a section
        # the workbook has, and the model has been observed synthesising one.
        combined_pdf = ingest.pdf_total_expenses
        combined_extracted = sum(
            line.ytd_actual or 0.0
            for line in ingest.lines
            if line.section.value not in _REVENUE_SECTIONS
        )
        # Reserve EXPENDITURES are as often off the operating statement as
        # reserve revenue is, so the same either-reading test applies.
        operating_only = sum(
            line.ytd_actual or 0.0
            for line in ingest.lines
            if line.section.value not in _REVENUE_SECTIONS and line.section.value != "RESERVES"
        )
        warn_limit = max(_tolerance(combined_pdf), abs(combined_pdf) * _EXPENSE_WARN_PCT)
        reconciled, reading, diff = _reconcile_fund_scope(
            combined_pdf, combined_extracted, operating_only, warn_limit
        )
        if reconciled and reading == "excluding reserves":
            ingest.missing_data.append(
                f"The report's expense total (${combined_pdf:,.2f}) covers the operating "
                f"fund only — the workbook's reserve expenditure of "
                f"${combined_extracted - operating_only:,.2f} is accounted for separately."
            )
        if not reconciled:
            mismatches.append(
                f"EXPENSES: extracted lines sum to ${combined_extracted:,.2f} but the "
                f'report\'s printed "TOTAL EXPENSES" is ${combined_pdf:,.2f} '
                f"(difference: ${diff:,.2f}) — extraction likely missed a line or "
                f"misread a value."
            )
        _note_section_drift(ingest, pdf_expense_sections)
    elif pdf_expense_sections:
        combined_pdf = sum(pdf_expense_sections.values())
        combined_extracted = sum(
            line.ytd_actual or 0.0
            for line in ingest.lines
            if line.section.value in pdf_expense_sections
        )
        diff = abs(combined_extracted - combined_pdf)
        warn_limit = max(_tolerance(combined_pdf), abs(combined_pdf) * _EXPENSE_WARN_PCT)

        if diff > warn_limit:
            per_section = "; ".join(
                f"{key}: extracted ${sum(
                    ln.ytd_actual or 0.0 for ln in ingest.lines if ln.section.value == key
                ):,.2f} vs PDF ${total:,.2f}"
                for key, total in sorted(pdf_expense_sections.items())
            )
            mismatches.append(
                f"EXPENSES (all sections combined): extracted lines sum to "
                f"${combined_extracted:,.2f} but PDF shows ${combined_pdf:,.2f} "
                f"(difference: ${diff:,.2f}) — extraction likely missed a line or "
                f"misread a value. By section: {per_section}"
            )
        else:
            _note_section_drift(ingest, pdf_expense_sections)

    if mismatches:
        raise CrossCheckFailed(mismatches)
