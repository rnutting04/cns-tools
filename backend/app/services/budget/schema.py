# app/services/budget/schema.py
from enum import Enum

from pydantic import BaseModel, computed_field


class BudgetSection(str, Enum):
    REVENUE_OPERATING = "REVENUE_OPERATING"
    REVENUE_RESERVES = "REVENUE_RESERVES"
    ADMINISTRATION = "ADMINISTRATION"
    MAINTENANCE = "MAINTENANCE"
    OTHER = "OTHER"
    UTILITIES = "UTILITIES"
    RESERVES = "RESERVES"


class FormattingConfig(BaseModel):
    company_footer: str = "C&S Community Management"
    draft_label: str = "Draft 1"


# Derived once from the instructions document; updated out-of-band when instructions change.
FORMATTING = FormattingConfig()


class BudgetLine(BaseModel):
    code: str
    label: str
    section: BudgetSection
    gl_account: str | None
    prior_year: float | None = None
    projected: float | None = None
    proposed: float | None = None
    note: str | None = None
    is_computed: bool = False
    annualization_review_flag: bool = False


class ReserveItem(BaseModel):
    code: str
    label: str
    total_life_years: int
    remaining_life_years: int
    replacement_cost: float
    current_balance: float
    required_deposit: float | None = None

    @computed_field
    @property
    def net_additional_needed(self) -> float:
        return self.replacement_cost - self.current_balance


# --- Stage 1 output ----------------------------------------------------------


class IngestedLine(BaseModel):
    """A single budget line. label/section/prior_year from Excel parsing; ytd_actual from AI."""

    label: str
    gl_account: str | None = None
    section: BudgetSection
    ytd_actual: float | None = None
    prior_year: float | None = None
    annualization_review: bool = False


class IngestResult(BaseModel):
    """Raw output of Stage 1 — merged from Excel parsing (prior_year) and AI extraction (ytd_actual)."""

    months_elapsed: int | None = None
    lines: list[IngestedLine]
    reserve_balances: dict[str, float] = {}
    # Section subtotals as printed in the PDF — used by Stage 1.5 cross-check.
    pdf_section_totals: dict[str, float] = {}
    missing_data: list[str] = []


# --- AI extraction schema (tool input for Stage 1 LLM call) ------------------


class AIExtractedLine(BaseModel):
    """One line returned by the AI from PDF-only extraction. No prior_year — that comes from Excel."""

    label: str
    gl_account: str | None = None
    section: BudgetSection
    ytd_actual: float | None = None
    annualization_review: bool = False


class AIExtractionResult(BaseModel):
    """What the LLM returns after reading only the PDF and the provided line list."""

    months_elapsed: int | None = None
    lines: list[AIExtractedLine]
    reserve_balances: dict[str, float] = {}
    pdf_section_totals: dict[str, float] = {}
    missing_data: list[str] = []


# --- Assembled output --------------------------------------------------------


class BudgetOutput(BaseModel):
    """Fully assembled budget — output of Stage 3, gate for Stage 4, input to Stage 5."""

    association_name: str
    budget_year: int
    months_elapsed: int
    lines: list[BudgetLine]
    reserve_items: list[ReserveItem]
    missing_data: list[str] = []
