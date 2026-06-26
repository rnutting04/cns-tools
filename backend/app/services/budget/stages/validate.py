# app/services/budget/stages/validate.py
#
# Stage 4 — Validate (hard gate)
#
# Runs all checks from the spec (section 6) against the assembled BudgetOutput.
# Structural and arithmetic failures halt the pipeline (raise ValidationFailed).
# Sanity checks collect review flags but do not halt.

from app.services.budget.exceptions import ValidationFailed
from app.services.budget.schema import BudgetOutput, BudgetSection

_TOLERANCE = 0.01  # float rounding tolerance for arithmetic checks


def _lines_by_code(budget: BudgetOutput) -> dict:
    return {l.code: l for l in budget.lines}


def _member_lines(budget: BudgetOutput, section: BudgetSection) -> list:
    return [l for l in budget.lines if l.section == section and not l.is_computed]


def _sum_members(budget: BudgetOutput, section: BudgetSection, col: str) -> float:
    return sum(getattr(l, col) or 0.0 for l in _member_lines(budget, section))


def run(budget: BudgetOutput) -> list[str]:
    """
    Stage 4: validate the assembled budget.

    Returns a list of sanity-flag messages (non-fatal review items).
    Raises ValidationFailed if any structural or arithmetic check fails.
    """
    errors: list[str] = []
    review: list[str] = []
    by_code = _lines_by_code(budget)

    # --- Structural checks (halt on fail) ------------------------------------

    for line in budget.lines:
        if not line.is_computed:
            # proposed must always be present — it's the output of the budget.
            if line.proposed is None:
                errors.append(f"[structural] '{line.label}' is missing proposed")
        if not line.code:
            errors.append(f"[structural] A line is missing a code (label: '{line.label}')")
        if not line.section:
            errors.append(f"[structural] '{line.label}' is missing a section")

    income_sections = [BudgetSection.REVENUE_OPERATING, BudgetSection.REVENUE_RESERVES]
    expense_sections = [
        BudgetSection.ADMINISTRATION,
        BudgetSection.MAINTENANCE,
        BudgetSection.UTILITIES,
        BudgetSection.OTHER,
        BudgetSection.RESERVES,
    ]
    # --- Arithmetic checks (halt on fail) ------------------------------------

    for col in ("prior_year", "projected", "proposed"):
        for section in income_sections + expense_sections:
            member_sum = _sum_members(budget, section, col)
            subtotal_code = f"subtotal_{section.value.lower()}"
            subtotal_line = by_code.get(subtotal_code)
            if subtotal_line:
                subtotal_val = getattr(subtotal_line, col) or 0.0
                if abs(member_sum - subtotal_val) > _TOLERANCE:
                    errors.append(
                        f"[arithmetic] {section.value} subtotal mismatch in '{col}': "
                        f"members sum to {member_sum:.2f}, subtotal shows {subtotal_val:.2f}"
                    )

        total_income_val = sum(_sum_members(budget, s, col) for s in income_sections)
        total_expense_val = sum(_sum_members(budget, s, col) for s in expense_sections)

        ti = by_code.get("total_income")
        te = by_code.get("total_operating_and_reserves")
        sur = by_code.get("surplus")

        if ti and abs((getattr(ti, col) or 0) - total_income_val) > _TOLERANCE:
            errors.append(
                f"[arithmetic] Total Income mismatch in '{col}': "
                f"expected {total_income_val:.2f}, got {getattr(ti, col):.2f}"
            )
        if te and abs((getattr(te, col) or 0) - total_expense_val) > _TOLERANCE:
            errors.append(
                f"[arithmetic] Total Operating and Reserves mismatch in '{col}': "
                f"expected {total_expense_val:.2f}, got {getattr(te, col):.2f}"
            )
        if ti and te and sur:
            expected_surplus = (getattr(ti, col) or 0) - (getattr(te, col) or 0)
            actual_surplus = getattr(sur, col) or 0
            if abs(expected_surplus - actual_surplus) > _TOLERANCE:
                errors.append(
                    f"[arithmetic] SURPLUS mismatch in '{col}': "
                    f"expected {expected_surplus:.2f}, got {actual_surplus:.2f}"
                )

    for item in budget.reserve_items:
        if item.remaining_life_years < 0:
            errors.append(
                f"[arithmetic] Reserve '{item.label}' has negative remaining_life_years "
                f"({item.remaining_life_years})"
            )

    if errors:
        raise ValidationFailed(errors)

    # --- Sanity checks (flag, do not halt) ------------------------------------

    for line in budget.lines:
        if not line.is_computed:
            if line.prior_year is None:
                review.append(
                    f"[sanity] '{line.label}' has no prior-year amount — new line not in last year's budget"
                )
            if line.projected is None:
                review.append(
                    f"[sanity] '{line.label}' has no projected value — no YTD actual in the financial report"
                )
            if line.proposed is None and (line.prior_year or 0) != 0:
                review.append(
                    f"[sanity] '{line.label}' proposed is blank but prior_year was "
                    f"{line.prior_year} — possible omission"
                )
            if line.prior_year and line.proposed is not None:
                ratio = abs(line.proposed - line.prior_year) / line.prior_year
                if ratio > 0.40:
                    review.append(
                        f"[sanity] '{line.label}' proposed ({line.proposed:.0f}) differs "
                        f"from prior_year ({line.prior_year:.0f}) by "
                        f"{ratio * 100:.0f}% — flag for review"
                    )
            if line.annualization_review_flag:
                review.append(
                    f"[sanity] '{line.label}' — straight annualization may be unreliable "
                    f"(known renewal or lumpy cost). Review projected value."
                )

    return review
