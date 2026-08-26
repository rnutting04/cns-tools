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
            # Qualified by section: a sheet can reuse one heading for two
            # different sections (MCP has "RESERVES" as both a revenue and an
            # expense header), and an unqualified key would merge them.
            subtotal_group=(
                f"{ingested.section.value}::{ingested.source_section}"
                if ingested.source_section
                else ingested.section.value
            ),
        )
        lines_by_section[ingested.section].append(line)

    # Build output lines: member lines followed by a subtotal row per group.
    #
    # A group is the workbook's OWN section heading where it has one, so a sheet
    # that keeps "BUILDING AND GROUNDS" and "MAINTENANCE" apart — each with its
    # own printed subtotal — gets a subtotal for each, written back into its own
    # row. Grouping by BudgetSection alone merged them into a single figure and
    # left the second printed subtotal stale. Groups stay in sheet order within
    # their section, so the output mirrors the source layout.
    all_lines: list[BudgetLine] = []
    for section in SECTION_ORDER:
        members = lines_by_section.get(section, [])
        if not members:
            continue

        groups: dict[str, list[BudgetLine]] = {}
        for member in members:
            groups.setdefault(member.subtotal_group or section.value, []).append(member)

        for group_key, group_members in groups.items():
            all_lines.extend(group_members)
            # Label the subtotal after the sheet's heading when the section is
            # split, so render matches it to that heading's own TOTAL row.
            source_label = group_key.split("::", 1)[-1]
            label = SUBTOTAL_LABELS[section] if len(groups) == 1 else f"Total {source_label.title()}"
            all_lines.append(
                BudgetLine(
                    code=f"subtotal_{_make_code(group_key)}",
                    label=label,
                    section=section,
                    gl_account=None,
                    prior_year=_subtotal(group_members, "prior_year"),
                    projected=_subtotal(group_members, "projected"),
                    proposed=_subtotal(group_members, "proposed"),
                    is_computed=True,
                    subtotal_group=group_key,
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
    # Prefer the schedule read straight from the workbook's reserve sheet; fall
    # back to one supplied by the caller. A component at remaining life 0 is due
    # this year, so the decrement is floored rather than allowed to go negative.
    schedule = ingest.reserve_schedule or prior_reserve_schedule or []
    reserve_items: list[ReserveItem] = []
    for entry in schedule:
        reserve_items.append(
            ReserveItem(
                code=_make_code(entry["label"]),
                label=entry["label"],
                total_life_years=entry["total_life_years"],
                remaining_life_years=max(0, entry["remaining_life_years"] - 1),
                replacement_cost=entry["replacement_cost"],
                # Workbook balance when we have one; otherwise whatever the AI
                # recovered from the PDF.
                current_balance=(
                    entry.get("current_balance")
                    if entry.get("current_balance") is not None
                    else ingest.reserve_balances.get(entry["label"], 0.0)
                ),
                required_deposit=entry.get("required_deposit"),
            )
        )

    return BudgetOutput(
        association_name=association_name,
        budget_year=budget_year,
        months_elapsed=ingest.months_elapsed or 1,
        lines=all_lines,
        reserve_items=reserve_items,
        missing_data=ingest.missing_data,
        subtotal_rows=ingest.subtotal_rows,
    )
