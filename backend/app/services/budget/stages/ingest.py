# app/services/budget/stages/ingest.py
#
# Stage 1 — Ingest
#
# Two sequential sub-steps:
#   A. Code reads the prior-year budget workbook to extract line labels,
#      sections and prior_year amounts. All layout decisions come from
#      app.services.budget.layout, which render.py shares. Nothing about
#      column selection is delegated to the AI.
#   B. AI reads only the PDF financial report to extract YTD actuals for each
#      of the labels provided from sub-step A.
#
# Results are merged: labels / sections / prior_year from A, ytd_actual from B.
#
# This is the only stage that calls an LLM; all subsequent stages are deterministic.

import base64
import re
from collections.abc import Callable
from pathlib import Path

from app.config.settings import settings
from app.services.budget import layout as layout_mod
from app.services.budget.exceptions import IngestFailed
from app.services.budget.layout import to_number as _to_number
from app.services.budget.reserves import parse_reserve_schedule
from app.services.budget.schema import (
    AIExtractionResult,
    IngestedLine,
    IngestResult,
)
from app.services.budget.workbook import _is_xls, load_workbook_any

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "ingest.txt"


def _parse_excel_budget(
    xlsx_bytes: bytes,
    budget_year: int,
    prior_budget_filename: str = "",
    layout_profile=None,
) -> tuple[list[dict], layout_mod.SheetLayout]:
    """
    Read the prior-year budget workbook and return
        ([{label, section, prior_year, note}], SheetLayout)

    All structural decisions — which sheet, which column holds labels, which
    column holds last year's adopted amounts, which rows start a section — are
    made by app.services.budget.layout, which the render stage also uses. That
    shared module is the only place those rules live, so ingest and render can
    no longer disagree about the shape of the same workbook.
    """
    wb = load_workbook_any(xlsx_bytes, prior_budget_filename, data_only=True)
    lay = layout_mod.build_layout(wb, budget_year)

    # A layout a human already confirmed overrides detection, including any
    # corrections they made to the sheet or column choices.
    if layout_profile is not None:
        from app.services.budget.layout_profiles import apply_profile

        lay = apply_profile(lay, layout_profile)

    if lay.sheet_title not in wb.sheetnames:
        raise ValueError(
            f"Sheet {lay.sheet_title!r} is not in this workbook "
            f"(has: {', '.join(wb.sheetnames)})"
        )
    ws = wb[lay.sheet_title]

    lines: list[dict] = []
    current = None
    current_source = None  # the sheet's own header text for the active section

    for row in range(lay.data_start_row, ws.max_row + 1):
        raw = ws.cell(row=row, column=lay.label_col).value
        if raw is None:
            continue
        label = str(raw).strip()
        if not label:
            continue

        # A section header row switches the active section and is not itself an item.
        if row in lay.section_rows:
            current = lay.section_rows[row]
            current_source = lay.section_source_labels.get(row)
            continue

        if layout_mod.is_total_row(label) or layout_mod.is_junk_row(label):
            continue

        # Rows before the first section header have no home; skip them rather
        # than guessing a section and inflating a subtotal.
        if current is None:
            continue

        prior = (
            _to_number(ws.cell(row=row, column=lay.prior_col).value)
            if lay.prior_col is not None
            else None
        )

        # A row with no amount in ANY value column is a spacer, not a line item.
        if prior is None and not any(
            _to_number(ws.cell(row=row, column=v.col).value) is not None for v in lay.value_cols
        ):
            continue

        # The workbook's GL code is the most reliable way to match a line to the
        # financial report: the two spell labels differently ("Assessments" in
        # the budget vs "Member Assessments" in the report) but agree on the
        # account number.
        gl = None
        if lay.gl_col is not None:
            gv = ws.cell(row=row, column=lay.gl_col).value
            if gv is not None:
                gs = str(gv).strip()
                if gs.endswith(".0"):
                    gs = gs[:-2]
                if re.fullmatch(r"\d{4,5}[a-z]?", gs, re.I):
                    gl = gs

        note = None
        if lay.notes_col is not None:
            nv = ws.cell(row=row, column=lay.notes_col).value
            if isinstance(nv, str) and nv.strip():
                note = nv.strip()

        lines.append(
            {
                "label": label,
                "gl_account": gl,
                "section": current,
                "source_section": current_source,
                "prior_year": prior,
                "note": note,
            }
        )

    # Check the parse against the workbook's own arithmetic before trusting it.
    # A confirmed profile has already been signed off, so it is not re-flagged.
    if layout_profile is None:
        lay.warnings.extend(layout_mod.self_check(ws, lay, lines))
    return lines, lay


def _parse_reserves(xlsx_bytes: bytes, budget_year: int, filename: str = "") -> list[dict]:
    """Read the reserve study from the workbook, or [] if it has no reserve sheet."""
    wb = load_workbook_any(xlsx_bytes, filename, data_only=True)
    return parse_reserve_schedule(wb, layout_mod.build_layout(wb, budget_year))


def _format_line_list(excel_lines: list[dict]) -> str:
    """
    Format the Excel-extracted line list as text for the AI prompt.

    Labels that appear in more than one section are called out explicitly.
    GOR carries "Assessments" in both REVENUE_OPERATING ($1.3M) and
    REVENUE_RESERVES ($256k); sent as two identical bare labels, the model
    returned a single entry and the operating assessments — the association's
    largest revenue line — went missing, which failed cross-check by $673k.
    """
    from collections import defaultdict

    by_section: dict[str, list[str]] = defaultdict(list)
    sections_for_label: dict[str, set[str]] = defaultdict(set)
    for line in excel_lines:
        label = line["label"]
        gl = line.get("gl_account")
        by_section[line["section"].value].append(f"[{gl}] {label}" if gl else label)
        sections_for_label[label.strip()].add(line["section"].value)

    section_order = [
        "REVENUE_OPERATING",
        "REVENUE_RESERVES",
        "ADMINISTRATION",
        "MAINTENANCE",
        "UTILITIES",
        "OTHER",
        "RESERVES",
    ]
    parts = [
        "BUDGET LINE ITEMS (match each to its YTD actual in the PDF).",
        "A leading [nnnn] is that line's GL account number in the budget workbook.",
        "MATCH ON THE GL NUMBER FIRST — the report often words a line differently",
        "from the workbook (workbook 'Assessments' = report 'Member Assessments',",
        "both GL 5000). Return the label WITHOUT the [nnnn] prefix, exactly as",
        "written below, and put the account number in gl_account.",
    ]
    for sec in section_order:
        labels = by_section.get(sec, [])
        if labels:
            parts.append(f"\n{sec}:")
            for lbl in labels:
                parts.append(f"  - {lbl}")

    # Labels are kept verbatim above (the model must echo them back exactly), so
    # repeats are disambiguated here instead of inline.
    repeated = {lbl: secs for lbl, secs in sections_for_label.items() if len(secs) > 1}
    if repeated:
        parts.append(
            "\nIMPORTANT — these labels appear under more than one section above. "
            "These are DIFFERENT lines with different amounts in the report. Return a "
            "separate entry for each, using the same label but the matching section:"
        )
        for lbl, secs in sorted(repeated.items()):
            parts.append(f"  - {lbl!r}: appears under {', '.join(sorted(secs))}")

    return "\n".join(parts)


def run(
    financial_report_bytes: bytes,
    financial_report_filename: str,
    prior_budget_bytes: bytes,
    prior_budget_filename: str,
    budget_year: int,
    on_step: Callable[[str], None] | None = None,
    layout_profile=None,
) -> IngestResult:
    """
    Stage 1: extract raw values from both input files.

    Sub-step A — code parses the xlsx to get labels, sections, and prior_year.
    Sub-step B — AI reads the PDF to get YTD actuals for each label.
    Results are merged into IngestResult.

    Raises IngestFailed if the xlsx cannot be parsed or if the LLM call fails.
    """
    # ── Sub-step A: deterministic Excel parsing ───────────────────────────────
    if on_step:
        on_step("reading_excel")
    try:
        excel_lines, sheet_layout = _parse_excel_budget(
            prior_budget_bytes, budget_year, prior_budget_filename, layout_profile
        )
    except Exception as exc:
        raise IngestFailed(f"Failed to parse prior-year budget xlsx: {exc}") from exc

    if not excel_lines:
        raise IngestFailed(
            "No line items found in the prior-year budget workbook "
            f"(read sheet '{sheet_layout.sheet_title}'). "
            "Confirm the file has a recognizable budget column structure."
        )

    # Structural doubts are surfaced, never swallowed. These are the conditions
    # that used to produce a confident but wrong parse — e.g. every line landing
    # in one section because no section header was recognized.
    layout_warnings = list(sheet_layout.warnings)
    layout_fingerprint = sheet_layout.signature
    sheet_subtotal_rows = dict(sheet_layout.subtotal_rows)

    # Legacy .xls inputs are converted to xlsx to be readable at all, and that
    # conversion cannot carry formulas: xlrd exposes only each cell's cached
    # value, never the formula behind it. Cell styling survives, but every
    # =SUM() becomes a static number. Native .xlsx files are passed through
    # untouched and keep their formulas, so the fix is to re-save the workbook
    # as .xlsx in Excel before uploading.
    legacy_xls_warning: list[str] = []
    if _is_xls(prior_budget_bytes, prior_budget_filename):
        legacy_xls_warning.append(
            "The prior-year budget was a legacy .xls file. Converting it to .xlsx "
            "preserved the layout and formatting but replaced every formula with "
            "its last calculated value. Re-save the workbook as .xlsx in Excel and "
            "re-run to keep the formulas live."
        )

    # Reserve study straight from the workbook. When present it supersedes the
    # AI's PDF-derived reserve balances below — the workbook numbers are exact.
    try:
        reserve_schedule = _parse_reserves(prior_budget_bytes, budget_year, prior_budget_filename)
    except Exception:  # a malformed reserve tab must never fail the whole run
        reserve_schedule = []
    excel_reserve_balances = {
        r["label"]: r["current_balance"] for r in reserve_schedule if r.get("current_balance")
    }

    # ── DEBUG FLAG ────────────────────────────────────────────────────────────
    # Set to True to skip the AI call entirely. The pipeline will run with
    # ytd_actual=None for every line, so projected stays blank and proposed
    # falls back to prior_year. Use this to verify the Excel column-copy logic
    # is producing the right numbers before re-enabling the AI.
    _DEBUG_SKIP_AI = False
    if _DEBUG_SKIP_AI:
        merged = [
            IngestedLine(
                label=xl["label"],
                section=xl["section"],
                prior_year=xl["prior_year"],
                ytd_actual=None,
                source_note=xl.get("note"),
                source_section=xl.get("source_section"),
            )
            for xl in excel_lines
        ]
        return IngestResult(
            months_elapsed=6,
            lines=merged,
            missing_data=["[DEBUG] AI call skipped — verifying Excel column copy only"]
            + legacy_xls_warning,
            layout_warnings=layout_warnings,
            layout_fingerprint=layout_fingerprint,
            reserve_schedule=reserve_schedule,
            reserve_balances=excel_reserve_balances,
            subtotal_rows=sheet_subtotal_rows,
        )

    # ── Sub-step B: AI extracts YTD actuals from the PDF ─────────────────────
    if on_step:
        on_step("extracting")
    try:
        from anthropic import Anthropic
    except ImportError as e:
        raise IngestFailed("anthropic is not installed — run: pip install anthropic") from e

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    system_prompt = _PROMPT_PATH.read_text()
    line_list_text = _format_line_list(excel_lines)

    pdf_b64 = base64.standard_b64encode(financial_report_bytes).decode()
    user_content: list[dict] = [
        {"type": "text", "text": f"INCOME AND EXPENSE REPORT ({financial_report_filename}):"},
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": pdf_b64,
            },
        },
        {"type": "text", "text": line_list_text},
    ]

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=16384,
            system=system_prompt,
            tools=[
                {
                    "name": "ingest_result",
                    "description": "YTD actuals and supporting data extracted from the PDF.",
                    "input_schema": AIExtractionResult.model_json_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": "ingest_result"},
            messages=[{"role": "user", "content": user_content}],
        )
    except Exception as exc:
        raise IngestFailed(f"LLM call failed: {exc}") from exc

    tool_block = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_block is None:
        raise IngestFailed(
            "LLM did not return structured output — no tool_use block in response. "
            f"Stop reason: {response.stop_reason}"
        )

    # The model sometimes emits null for a section total or reserve balance it
    # couldn't find in the PDF. Those dict fields are typed float, so drop the
    # null entries (a missing key is fine) rather than failing the whole ingest.
    tool_input = dict(tool_block.input)
    for _dict_field in ("pdf_section_totals", "reserve_balances"):
        raw = tool_input.get(_dict_field)
        if isinstance(raw, dict):
            tool_input[_dict_field] = {k: v for k, v in raw.items() if v is not None}

    try:
        ai_result = AIExtractionResult(**tool_input)
    except Exception as exc:
        raise IngestFailed(f"LLM returned invalid structured output: {exc}") from exc

    if not ai_result.months_elapsed or ai_result.months_elapsed <= 0:
        detail = (
            " The model reported: " + "; ".join(ai_result.missing_data)
            if ai_result.missing_data
            else ""
        )
        raise IngestFailed(
            "Could not determine months elapsed from the financial report. "
            "Confirm the report has a clear period header such as "
            "'For the Period Ending August 31, 2025'." + detail
        )

    # ── Merge: Excel (label/section/prior_year) + AI (ytd_actual/gl_account) ─
    # Build both an exact lookup and a case-insensitive fallback so that minor
    # AI casing differences ("Member Assessments" vs "Member ASSESSMENTS") still
    # match the Excel label rather than creating a phantom duplicate line.
    # Keyed by (section, label) FIRST. Keying on label alone silently collided
    # whenever a workbook repeated a label across sections — GOR's "Assessments"
    # appears in both REVENUE_OPERATING and REVENUE_RESERVES, so the last one won
    # and both Excel rows received the same YTD actual.
    ai_by_section_label: dict[tuple[str, str], object] = {}
    for line in ai_result.lines:
        ai_by_section_label.setdefault((line.section.value, line.label.strip().lower()), line)

    # GL account is the strongest key — it survives the report and the workbook
    # wording a line differently, which plain label matching does not.
    ai_by_gl: dict[str, object] = {}
    for line in ai_result.lines:
        if line.gl_account:
            ai_by_gl.setdefault(str(line.gl_account).strip().lower(), line)

    ai_by_label_exact: dict[str, object] = {line.label: line for line in ai_result.lines}
    ai_by_label_lower: dict[str, object] = {}
    for line in ai_result.lines:
        ai_by_label_lower.setdefault(line.label.strip().lower(), line)

    # Labels the workbook repeats across sections must only ever match on the
    # section-qualified key, never on the ambiguous label-only fallback.
    ambiguous_labels = {
        label
        for label in {xl["label"].strip().lower() for xl in excel_lines}
        if len({xl["section"].value for xl in excel_lines if xl["label"].strip().lower() == label})
        > 1
    }

    excel_label_set = {xl["label"] for xl in excel_lines}
    excel_label_set_lower = {xl["label"].strip().lower() for xl in excel_lines}

    merged: list[IngestedLine] = []

    for xl in excel_lines:
        key = xl["label"].strip().lower()
        gl_key = str(xl.get("gl_account") or "").strip().lower()
        ai_line = ai_by_gl.get(gl_key) if gl_key else None
        if ai_line is None:
            ai_line = ai_by_section_label.get((xl["section"].value, key))
        if ai_line is None and key not in ambiguous_labels:
            ai_line = ai_by_label_exact.get(xl["label"]) or ai_by_label_lower.get(key)
        merged.append(
            IngestedLine(
                label=xl["label"],
                section=xl["section"],
                prior_year=xl["prior_year"],
                gl_account=xl.get("gl_account") or (ai_line.gl_account if ai_line else None),
                ytd_actual=ai_line.ytd_actual if ai_line else None,
                annualization_review=ai_line.annualization_review if ai_line else False,
                source_note=xl.get("note"),
                source_section=xl.get("source_section"),
            )
        )

    # Lines the AI found in the PDF that aren't in the Excel (e.g., new revenue items).
    # Skip if the AI label is a case-variant of an existing Excel label — that means
    # the AI slightly mis-cased a provided label rather than returning a genuinely new line.
    for ai_line in ai_result.lines:
        if (
            ai_line.label not in excel_label_set
            and ai_line.label.strip().lower() not in excel_label_set_lower
        ):
            merged.append(
                IngestedLine(
                    label=ai_line.label,
                    section=ai_line.section,
                    prior_year=None,
                    gl_account=ai_line.gl_account,
                    ytd_actual=ai_line.ytd_actual,
                    annualization_review=ai_line.annualization_review,
                )
            )

    if not merged:
        raise IngestFailed(
            "No lines were produced. "
            "Confirm the prior-year budget xlsx and the financial report are valid."
        )

    return IngestResult(
        months_elapsed=ai_result.months_elapsed,
        lines=merged,
        # Workbook-sourced balances win; the AI's PDF reading fills any gaps.
        reserve_balances={**ai_result.reserve_balances, **excel_reserve_balances},
        pdf_section_totals=ai_result.pdf_section_totals,
        pdf_total_revenue=ai_result.pdf_total_revenue,
        pdf_total_expenses=ai_result.pdf_total_expenses,
        missing_data=ai_result.missing_data + legacy_xls_warning,
        layout_warnings=layout_warnings,
        layout_fingerprint=layout_fingerprint,
        reserve_schedule=reserve_schedule,
        subtotal_rows=sheet_subtotal_rows,
    )
