# app/services/budget/service.py
#
# Public API for the budget pipeline. Framework-free: no FastAPI imports.
#
# Pipeline:
#   Stage 1   (ingest)      — Excel + PDF parsing; extracts prior_year amounts
#                             and YTD actuals, returns structured IngestResult
#   Stage 1.5 (cross_check) — verifies extracted line sums match PDF section totals
#   Stage 2   (project)     — annualizes YTD actuals; flags review lines
#   Stage 3   (assemble)    — populates BudgetOutput schema, computes totals
#   Stage 4   (validate)    — hard gate: halts on any structural/arithmetic failure
#   Stage 5   (render)      — writes .xlsx with live formulas

from collections.abc import Callable
from dataclasses import dataclass

from app.services.budget.exceptions import MissingInputFile
from app.services.budget.stages import assemble, cross_check, ingest, project, render, validate


@dataclass
class BudgetResult:
    xlsx_bytes: bytes
    review_flags: list[str]
    association_name: str
    budget_year: int


@dataclass
class LayoutPreview:
    """Stage-1A-only result: enough to judge the parse without spending an AI call."""

    lines: list[dict]
    layout: object  # SheetLayout
    all_sheets: list[str]
    reserve_items: list[dict]


def preview_layout(
    prior_budget_bytes: bytes,
    prior_budget_filename: str,
    budget_year: int,
    layout_profile=None,
) -> LayoutPreview:
    """
    Run only the deterministic Excel read, so a doubtful layout can be reviewed
    BEFORE any Anthropic call is made. Nothing here costs money or touches the PDF.
    """
    if not prior_budget_bytes:
        raise MissingInputFile("prior_budget is required")

    from app.services.budget.reserves import parse_reserve_schedule
    from app.services.budget.workbook import load_workbook_any

    lines, layout = ingest._parse_excel_budget(
        prior_budget_bytes, budget_year, prior_budget_filename, layout_profile
    )
    wb = load_workbook_any(prior_budget_bytes, prior_budget_filename, data_only=True)
    try:
        reserve_items = parse_reserve_schedule(wb, layout)
    except Exception:
        reserve_items = []

    return LayoutPreview(
        lines=lines,
        layout=layout,
        all_sheets=list(wb.sheetnames),
        reserve_items=reserve_items,
    )


def run_budget_pipeline(
    financial_report_bytes: bytes | None,
    financial_report_filename: str,
    prior_budget_bytes: bytes | None,
    prior_budget_filename: str,
    association_name: str,
    budget_year: int,
    prior_reserve_schedule: list[dict] | None = None,
    on_step: Callable[[str], None] | None = None,
    layout_profile=None,
) -> BudgetResult:
    """
    Run the full budget pipeline against the two uploaded files.

    Args:
        financial_report_bytes    — raw bytes of the monthly financial report (PDF)
        financial_report_filename — original filename (used to detect file type)
        prior_budget_bytes        — raw bytes of the prior-year adopted budget (xlsx or PDF)
        prior_budget_filename     — original filename
        association_name          — display name for the HOA
        budget_year               — the new year being budgeted (e.g. 2026)
        prior_reserve_schedule    — optional reserve items from last year's schedule
                                    (ignored when the workbook has its own reserve sheet)
        layout_profile            — a human-confirmed BudgetLayoutProfile to apply
                                    instead of auto-detecting the workbook layout

    Raises:
        MissingInputFile   — a required file was not provided
        IngestFailed       — PDF/xlsx could not be parsed or data is insufficient
        CrossCheckFailed   — extracted line sums don't reconcile with PDF totals
        ValidationFailed   — structural or arithmetic check failed
        RenderFailed       — xlsx generation produced errors
    """
    if not financial_report_bytes:
        raise MissingInputFile("financial_report is required")
    if not prior_budget_bytes:
        raise MissingInputFile("prior_budget is required")

    # Stage 1 — Ingest (emits "reading_excel" then "extracting" via on_step)
    ingest_result = ingest.run(
        financial_report_bytes=financial_report_bytes,
        financial_report_filename=financial_report_filename,
        prior_budget_bytes=prior_budget_bytes,
        prior_budget_filename=prior_budget_filename,
        budget_year=budget_year,
        on_step=on_step,
        layout_profile=layout_profile,
    )

    # Stage 1.5 — Cross-check
    if on_step:
        on_step("cross_check")
    cross_check.run(ingest_result)

    # Stage 2 — Project
    if on_step:
        on_step("calculating")
    projected, review_labels = project.run(ingest_result)

    # Stage 3 — Assemble
    if on_step:
        on_step("assembling")
    budget = assemble.run(
        ingest=ingest_result,
        projected=projected,
        review_labels=review_labels,
        association_name=association_name,
        budget_year=budget_year,
        prior_reserve_schedule=prior_reserve_schedule,
    )

    # Stage 4 — Validate (hard gate; fast enough to share the assembling step)
    review_flags = validate.run(budget)

    # Stage 5 — Render (edits the uploaded xlsx in place)
    if on_step:
        on_step("rendering")
    result = render.run(budget, review_flags, prior_budget_bytes)

    return BudgetResult(
        xlsx_bytes=result.xlsx_bytes,
        review_flags=result.review_flags,
        association_name=association_name,
        budget_year=budget_year,
    )
