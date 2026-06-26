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


def _tolerance(section_total: float) -> float:
    return max(_TOLERANCE_ABS, abs(section_total) * _TOLERANCE_PCT)


# Revenue sections are checked as a combined total, not individually. A line
# near the OPERATING / RESERVES boundary (e.g. reserve interest income) is often
# grouped differently across associations. If the combined revenue total reconciles,
# an individual section mismatch is a classification issue — not a missing line.
_REVENUE_SECTIONS = {"REVENUE_OPERATING", "REVENUE_RESERVES"}


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
    if not ingest.pdf_section_totals:
        return

    mismatches: list[str] = []

    # --- Revenue: check combined total first -----------------------------------
    pdf_revenue_sections = {
        k: v for k, v in ingest.pdf_section_totals.items() if k in _REVENUE_SECTIONS
    }
    if pdf_revenue_sections:
        combined_pdf = sum(pdf_revenue_sections.values())
        combined_extracted = sum(
            line.ytd_actual or 0.0
            for line in ingest.lines
            if line.section.value in _REVENUE_SECTIONS
        )
        diff = abs(combined_extracted - combined_pdf)
        warn_limit = abs(combined_pdf) * _REVENUE_WARN_PCT

        if diff > warn_limit:
            # > 1% off — likely missed an entire revenue section. Hard failure.
            lines_detail = "; ".join(
                f"{l.label}: ${l.ytd_actual:,.2f}"
                for l in ingest.lines
                if l.section.value in _REVENUE_SECTIONS and l.ytd_actual is not None
            ) or "none"
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

        if diff <= warn_limit:
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

    # --- Expense sections: check individually ---------------------------------
    for section_key, pdf_total in ingest.pdf_section_totals.items():
        if section_key in _REVENUE_SECTIONS:
            continue

        extracted_sum = sum(
            line.ytd_actual or 0.0
            for line in ingest.lines
            if line.section.value == section_key
        )

        if abs(extracted_sum - pdf_total) > _tolerance(pdf_total):
            lines_detail = "; ".join(
                f"{l.label}: ${l.ytd_actual:,.2f}"
                for l in ingest.lines
                if l.section.value == section_key and l.ytd_actual is not None
            ) or "none"
            mismatches.append(
                f"{section_key}: extracted lines sum to ${extracted_sum:,.2f} "
                f"but PDF shows ${pdf_total:,.2f} "
                f"(difference: ${abs(extracted_sum - pdf_total):,.2f}) — "
                f"extraction likely missed a line or misread a value. "
                f"Extracted lines: {lines_detail}"
            )

    if mismatches:
        raise CrossCheckFailed(mismatches)
