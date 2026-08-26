# app/services/budget/layout_profiles.py
#
# Decides whether a workbook's detected layout can be trusted to run unattended,
# and stores the layouts a human has confirmed.
#
# The gate:
#   - A CONFIRMED profile matching the workbook's structural signature
#     → run unattended.
#   - Anything else → park the job for one human confirmation.
#
# Confidence is not part of the decision. The worst failures this pipeline has
# had were confident parses that were silently wrong — every expense booked as
# revenue, or last year's amounts read from an "ACTUAL" column — and none of
# them raised a warning. A short confirmation is cheap; a budget built on a
# misread column is not.
#
# What makes that affordable at ~180 associations is the signature: it is a
# structural fingerprint that excludes amounts and names, so workbooks sharing a
# template share a signature. One review covers the whole family, this year and
# every year after — a handful of reviews in total, not one per association.

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.budget_layout_profile import BudgetLayoutProfile
from app.services.budget.layout import SheetLayout


def layout_to_dict(layout: SheetLayout) -> dict:
    """Serialize a detected layout for storage and for the review UI."""
    return {
        "sheet_title": layout.sheet_title,
        "header_row": layout.header_row,
        "label_col": layout.label_col,
        "gl_col": layout.gl_col,
        "prior_col": layout.prior_col,
        "projected_col": layout.projected_col,
        "proposed_col": layout.proposed_col,
        "notes_col": layout.notes_col,
        "reserve_sheet": layout.reserve_sheet,
        "data_start_row": layout.data_start_row,
        "section_rows": {str(r): s.value for r, s in sorted(layout.section_rows.items())},
        "value_cols": [
            {"col": v.col, "year": v.year, "role": v.role, "header": v.header}
            for v in layout.value_cols
        ],
        "warnings": list(layout.warnings),
        "signature": layout.signature,
    }


def apply_profile(layout: SheetLayout, profile: BudgetLayoutProfile) -> SheetLayout:
    """Overlay a confirmed profile's corrections onto a freshly detected layout."""
    layout.sheet_title = profile.sheet_title
    layout.header_row = profile.header_row
    layout.label_col = profile.label_col
    layout.prior_col = profile.prior_col
    layout.projected_col = profile.projected_col
    layout.proposed_col = profile.proposed_col
    layout.notes_col = profile.notes_col
    if profile.reserve_sheet:
        layout.reserve_sheet = profile.reserve_sheet
    # A confirmed profile is by definition no longer in doubt.
    layout.warnings = []
    return layout


def find_confirmed(db: Session, signature: str | None) -> BudgetLayoutProfile | None:
    if not signature:
        return None
    return (
        db.query(BudgetLayoutProfile)
        .filter(
            BudgetLayoutProfile.signature == signature,
            BudgetLayoutProfile.confirmed.is_(True),
        )
        .first()
    )


# Confirm the layout on EVERY run, even for a template already confirmed.
#
# While the parser is still being shaken out against real association files, a
# confirmation that takes seconds is worth far more than the runs it costs: the
# worst failures here were confident-but-wrong parses that balanced and raised
# no warning at all. Set this False once the templates have proven themselves,
# and confirmation drops back to once per template family — the stored profiles
# and signatures already work that way, so it is a one-line change.
ALWAYS_CONFIRM_TEMPLATE = True


def needs_review(db: Session, layout: SheetLayout) -> bool:
    """
    True when this layout must be confirmed by a human before the run continues.

    With ALWAYS_CONFIRM_TEMPLATE set, this is every run. Otherwise it is once per
    template family: the check is keyed on the layout signature rather than the
    association, so ~180 associations collapse to a handful of reviews, each paid
    once and reused every year after.
    """
    if ALWAYS_CONFIRM_TEMPLATE:
        return True
    return find_confirmed(db, layout.signature) is None


def record_pending(
    db: Session,
    layout: SheetLayout,
    association_name: str,
    filename: str,
) -> BudgetLayoutProfile:
    """
    Upsert an UNCONFIRMED profile for a layout awaiting review.

    Two jobs uploaded before anyone reviews share one pending row, so confirming
    once clears the backlog for that whole template family.
    """
    existing = (
        db.query(BudgetLayoutProfile)
        .filter(BudgetLayoutProfile.signature == layout.signature)
        .first()
    )
    if existing:
        existing.warnings = list(layout.warnings)
        db.commit()
        return existing

    data = layout_to_dict(layout)
    profile = BudgetLayoutProfile(
        signature=layout.signature,
        sheet_title=data["sheet_title"],
        header_row=data["header_row"],
        label_col=data["label_col"],
        prior_col=data["prior_col"],
        projected_col=data["projected_col"],
        proposed_col=data["proposed_col"],
        notes_col=data["notes_col"],
        reserve_sheet=data["reserve_sheet"],
        section_rows=data["section_rows"],
        value_cols=data["value_cols"],
        warnings=data["warnings"],
        confirmed=False,
        example_association=association_name,
        example_filename=filename,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def confirm(
    db: Session,
    signature: str,
    user_id,
    corrections: dict | None = None,
) -> BudgetLayoutProfile | None:
    """
    Mark a layout confirmed, optionally applying reviewer corrections.

    `corrections` may override sheet_title / label_col / prior_col /
    projected_col / proposed_col / notes_col — the fields the review UI exposes.
    """
    profile = (
        db.query(BudgetLayoutProfile).filter(BudgetLayoutProfile.signature == signature).first()
    )
    if profile is None:
        return None

    for field in (
        "sheet_title",
        "label_col",
        "prior_col",
        "projected_col",
        "proposed_col",
        "notes_col",
        "reserve_sheet",
    ):
        if corrections and corrections.get(field) is not None:
            setattr(profile, field, corrections[field])

    profile.confirmed = True
    profile.confirmed_by = user_id
    profile.confirmed_at = datetime.now(UTC)
    db.commit()
    db.refresh(profile)
    return profile


def mark_used(db: Session, profile: BudgetLayoutProfile) -> None:
    profile.use_count = (profile.use_count or 0) + 1
    db.commit()


_SECTION_ORDER = [
    "REVENUE_OPERATING",
    "REVENUE_RESERVES",
    "ADMINISTRATION",
    "MAINTENANCE",
    "UTILITIES",
    "OTHER",
    "RESERVES",
]


def build_review_payload(
    layout: SheetLayout,
    lines: list[dict],
    all_sheets: list[str],
    reserve_items: int = 0,
) -> dict:
    """
    Assemble what a reviewer needs to judge a parse in about a minute.

    Deliberately leads with the two things that actually reveal a bad parse —
    which sheet and which column were read, and whether the money balances —
    rather than a wall of line items.
    """
    # Grouped by the workbook's OWN heading, falling back to the normalized
    # section name. A sheet that keeps "BUILDING AND GROUNDS" apart from
    # "MAINTENANCE" shows as two rows here — matching what the reviewer sees in
    # Excel — instead of one merged figure they cannot reconcile against it.
    by_group: dict[str, dict] = {}
    for ln in lines:
        section = ln["section"].value
        key = ln.get("source_section") or section
        bucket = by_group.setdefault(
            key,
            {
                "section": section,
                "source_section": ln.get("source_section"),
                "label": key,
                "count": 0,
                "total": 0.0,
                "sample": [],
            },
        )
        bucket["count"] += 1
        bucket["total"] += ln["prior_year"] or 0.0
        # Every line, not a sample: the reviewer is checking that the parse
        # matches their spreadsheet, and a truncated list cannot show that.
        bucket["sample"].append(
            {"label": ln["label"], "amount": ln["prior_year"], "note": ln.get("note")}
        )

    _order = {key: i for i, key in enumerate(_SECTION_ORDER)}
    sections = sorted(by_group.values(), key=lambda b: _order.get(b["section"], 99))
    revenue = sum(s["total"] for s in sections if s["section"].startswith("REVENUE"))
    expenses = sum(s["total"] for s in sections if not s["section"].startswith("REVENUE"))

    prior = next((v for v in layout.value_cols if v.col == layout.prior_col), None)

    projected = next((v for v in layout.value_cols if v.col == layout.projected_col), None)
    proposed = next((v for v in layout.value_cols if v.col == layout.proposed_col), None)

    return {
        "signature": layout.signature,
        "sheet_title": layout.sheet_title,
        "all_sheets": all_sheets,
        "header_row": layout.header_row,
        "data_start_row": layout.data_start_row,
        "label_col": layout.label_col,
        "gl_col": layout.gl_col,
        "prior_col": layout.prior_col,
        "prior_col_header": prior.header if prior else None,
        "projected_col": layout.projected_col,
        "projected_col_header": projected.header if projected else None,
        "proposed_col": layout.proposed_col,
        "proposed_col_header": proposed.header if proposed else None,
        "notes_col": layout.notes_col,
        "reserve_sheet": layout.reserve_sheet,
        "reserve_items": reserve_items,
        # Which sheet row prints each section's subtotal — render writes the
        # =SUM into exactly these rows, so it is worth showing.
        "subtotal_rows": {group: row for group, row in sorted(layout.subtotal_rows.items())},
        "value_cols": [
            {"col": v.col, "year": v.year, "role": v.role, "header": v.header}
            for v in layout.value_cols
        ],
        "line_count": len(lines),
        "sections": sections,
        "revenue_total": revenue,
        "expense_total": expenses,
        "balanced": abs(revenue - expenses) <= max(1.0, revenue * 0.005),
        "notes_captured": sum(1 for ln in lines if ln.get("note")),
        "warnings": list(layout.warnings),
    }
