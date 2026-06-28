# app/services/budget/stages/assemble.py
#
# Stage 3 — Assemble
#
# Builds a fully populated BudgetOutput from the AI-extracted IngestResult and
# the projected values computed in Stage 2. No static GL mapping — line items
# and sections come directly from what the AI read out of the two input files.

import re
from collections import defaultdict

from app.services.budget.schema import (
    BudgetLine,
    BudgetOutput,
    BudgetSection,
    IngestResult,
    ReserveItem,
)

# Display order for sections in the output workbook.
SECTION_ORDER = [
    BudgetSection.REVENUE_OPERATING,
    BudgetSection.REVENUE_RESERVES,
    BudgetSection.ADMINISTRATION,
    BudgetSection.MAINTENANCE,
    BudgetSection.UTILITIES,
    BudgetSection.OTHER,
    BudgetSection.RESERVES,
]

SUBTOTAL_LABELS: dict[BudgetSection, str] = {
    # Labels must match the xlsx template row text so render.py can find the right row.
    # REVENUE_OPERATING and REVENUE_RESERVES share labels with their expense counterparts
    # ("Total Operating" / "Total Reserves") — render.py processes income sections first,
    # so the income rows are claimed before the expense rows.
    BudgetSection.REVENUE_OPERATING: "Total Operating",
    BudgetSection.REVENUE_RESERVES: "Total Reserves",
    BudgetSection.ADMINISTRATION: "Total Administration",
    BudgetSection.MAINTENANCE: "Total Maintenance",
    BudgetSection.UTILITIES: "Total Utilities",
    BudgetSection.OTHER: "Total Other",
    BudgetSection.RESERVES: "Total Reserves",
}


def _make_code(label: str) -> str:
    """Deterministic snake_case slug from a display label."""
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def _subtotal(lines: list[BudgetLine], col: str) -> float | None:
    vals = [getattr(ln, col) for ln in lines if not ln.is_computed]
    if not vals or all(v is None for v in vals):
        return None
    return sum(v or 0.0 for v in vals)


def run(
    ingest: IngestResult,
    projected: dict[str, float | None],
    review_labels: set[str],
    association_name: str,
    budget_year: int,
    prior_reserve_schedule: list[dict] | None = None,
) -> BudgetOutput:
    """
    Stage 3: assemble the full BudgetOutput from AI-extracted + projected values.

    Line items and sections come from IngestResult.lines — no static mapping.
    """
    # Group member lines by section, preserving the order the AI returned them.
    lines_by_section: dict[BudgetSection, list[BudgetLine]] = defaultdict(list)

    for ingested in ingest.lines:
        proj = projected.get(ingested.label)
        line = BudgetLine(
            code=_make_code(ingested.label),
            label=ingested.label,
            section=ingested.section,
            gl_account=ingested.gl_account,
            prior_year=ingested.prior_year,
            projected=proj,
            # If we have no YTD to annualize (reserve expenditures, unmatched lines),
            # carry the prior-year amount forward as the starting proposed value.
            proposed=proj if proj is not None else (ingested.prior_year or 0.0),
            annualization_review_flag=ingested.label in review_labels,
        )
        lines_by_section[ingested.section].append(line)

    # Build output lines: member lines followed by a subtotal row per section.
    all_lines: list[BudgetLine] = []
    for section in SECTION_ORDER:
        members = lines_by_section.get(section, [])
        if not members:
            continue
        all_lines.extend(members)
        all_lines.append(
            BudgetLine(
                code=f"subtotal_{section.value.lower()}",
                label=SUBTOTAL_LABELS[section],
                section=section,
                gl_account=None,
                prior_year=_subtotal(members, "prior_year"),
                projected=_subtotal(members, "projected"),
                proposed=_subtotal(members, "proposed"),
                is_computed=True,
            )
        )

    # Grand totals.
    income_sections = [BudgetSection.REVENUE_OPERATING, BudgetSection.REVENUE_RESERVES]
    operating_expense_sections = [
        BudgetSection.ADMINISTRATION,
        BudgetSection.MAINTENANCE,
        BudgetSection.UTILITIES,
        BudgetSection.OTHER,
    ]
    expense_sections = operating_expense_sections + [BudgetSection.RESERVES]

    def grand(sections: list[BudgetSection], col: str) -> float | None:
        vals = [_subtotal(lines_by_section.get(s, []), col) for s in sections]
        if not vals or all(v is None for v in vals):
            return None
        return sum(v or 0.0 for v in vals)

    total_income = BudgetLine(
        code="total_income",
        label="Total Income",
        section=BudgetSection.REVENUE_OPERATING,
        gl_account=None,
        prior_year=grand(income_sections, "prior_year"),
        projected=grand(income_sections, "projected"),
        proposed=grand(income_sections, "proposed"),
        is_computed=True,
    )
    # Matches spreadsheets that carry an intermediate "TOTAL OPERATING" row
    # (admin + maintenance + utilities + other, before reserves are added).
    total_operating = BudgetLine(
        code="total_operating",
        label="Total Operating",
        section=BudgetSection.ADMINISTRATION,
        gl_account=None,
        prior_year=grand(operating_expense_sections, "prior_year"),
        projected=grand(operating_expense_sections, "projected"),
        proposed=grand(operating_expense_sections, "proposed"),
        is_computed=True,
    )
    total_expense = BudgetLine(
        code="total_operating_and_reserves",
        label="Total Operating and Reserves",
        section=BudgetSection.ADMINISTRATION,
        gl_account=None,
        prior_year=grand(expense_sections, "prior_year"),
        projected=grand(expense_sections, "projected"),
        proposed=grand(expense_sections, "proposed"),
        is_computed=True,
    )
    surplus = BudgetLine(
        code="surplus",
        label="Surplus / (Deficit)",
        section=BudgetSection.REVENUE_OPERATING,
        gl_account=None,
        prior_year=(total_income.prior_year or 0) - (total_expense.prior_year or 0),
        projected=(total_income.projected or 0) - (total_expense.projected or 0),
        proposed=(total_income.proposed or 0) - (total_expense.proposed or 0),
        is_computed=True,
    )
    all_lines.extend([total_income, total_operating, total_expense, surplus])

    # Reserve schedule — decrement remaining_life_years by one.
    reserve_items: list[ReserveItem] = []
    for entry in prior_reserve_schedule or []:
        reserve_items.append(
            ReserveItem(
                code=_make_code(entry["label"]),
                label=entry["label"],
                total_life_years=entry["total_life_years"],
                remaining_life_years=entry["remaining_life_years"] - 1,
                replacement_cost=entry["replacement_cost"],
                current_balance=ingest.reserve_balances.get(entry["label"], 0.0),
            )
        )

    return BudgetOutput(
        association_name=association_name,
        budget_year=budget_year,
        months_elapsed=ingest.months_elapsed or 1,
        lines=all_lines,
        reserve_items=reserve_items,
        missing_data=ingest.missing_data,
    )
