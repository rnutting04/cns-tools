# app/services/budget/stages/project.py
#
# Stage 2 — Project
#
# Annualizes YTD actuals from the IngestResult and flags lines for human review.
# All flagging is deterministic — no LLM required.

from app.services.budget.schema import BudgetSection, IngestResult

# Reserve capital expenditures should never be straight-annualized.
_ALWAYS_FLAG_SECTIONS = {BudgetSection.RESERVES}

# Label keywords indicating lump-sum or one-time payments.
_FLAG_LABEL_KEYWORDS = [
    "insurance",
    "premium",
    "bond",
    "warranty",
    "legal",
    "attorney",
    "special assessment",
    "special assess",
    "tax",
    "permit",
    "license",
]

# Projected deviates by more than this factor from prior year → flag for review.
_OUTLIER_HIGH = 2.0
_OUTLIER_LOW = 0.30


def _should_flag(
    label: str, section: BudgetSection, projected: float | None, prior_year: float | None
) -> bool:
    if section in _ALWAYS_FLAG_SECTIONS:
        return True

    label_lower = label.lower()
    if any(kw in label_lower for kw in _FLAG_LABEL_KEYWORDS):
        return True

    if projected is not None and prior_year and prior_year != 0:
        ratio = projected / prior_year
        if ratio > _OUTLIER_HIGH or ratio < _OUTLIER_LOW:
            return True

    return False


def run(ingest: IngestResult) -> tuple[dict[str, float | None], set[str]]:
    """
    Stage 2: annualize YTD actuals and determine which lines need human review.

    projected = ytd_actual / months_elapsed * 12

    Flagging rules (applied in order, first match wins):
      1. Section == RESERVES: always flag (capital expenditures annualize poorly)
      2. Label keyword match (insurance, legal, premium, etc.)
      3. Statistical outlier: projected deviates >2× or <0.3× from prior year

    Returns:
        projected     — { line_label: annualized_amount | None }
        review_labels — labels requiring human review in the output workbook
    """
    months = ingest.months_elapsed or 1

    projected: dict[str, float | None] = {}
    review_labels: set[str] = set()

    for line in ingest.lines:
        proj = line.ytd_actual / months * 12 if line.ytd_actual is not None else None
        projected[line.label] = proj

        if _should_flag(line.label, line.section, proj, line.prior_year):
            review_labels.add(line.label)

    return projected, review_labels
