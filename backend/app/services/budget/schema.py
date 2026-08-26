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
    # Which subtotal group this line belongs to (a member line) or totals (a
    # subtotal line). Defaults to the BudgetSection, but where a workbook keeps
    # two sections that normalize to the same one, each group is that sheet's own
    # heading — so render writes a separate =SUM into each printed subtotal row
    # instead of merging them.
    subtotal_group: str | None = None


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
    # Analyst rationale carried over from the workbook's comments column
    # (MOR column K, PRD "COMMENTS") — e.g. "Increase 5%", "Audit not required".
    source_note: str | None = None
    # The section heading as written in the workbook ("BUILDING AND GROUNDS").
    # `section` normalizes for the pipeline's arithmetic; this preserves the
    # sheet's own structure so each section keeps its own subtotal row.
    source_section: str | None = None


class IngestResult(BaseModel):
    """Raw output of Stage 1 — merged from Excel parsing (prior_year) and AI extraction (ytd_actual)."""

    months_elapsed: int | None = None
    lines: list[IngestedLine]
    reserve_balances: dict[str, float] = {}
    # Section subtotals as printed in the PDF — advisory only, since a report's
    # section headings often group lines differently from the workbook's.
    pdf_section_totals: dict[str, float] = {}
    # Printed grand totals — what Stage 1.5 actually reconciles against.
    pdf_total_revenue: float | None = None
    pdf_total_expenses: float | None = None
    missing_data: list[str] = []
    # Structural doubts from workbook layout detection. Non-empty means the
    # parse may be confident-but-wrong and should be confirmed by a human.
    layout_warnings: list[str] = []
    # Structural signature of the source workbook, used to reuse an already
    # confirmed layout across the associations that share a template.
    layout_fingerprint: str | None = None
    # Reserve study read straight from the workbook's reserve sheet, when it has
    # one. Preferred over AI-extracted reserve balances — same numbers, exact.
    reserve_schedule: list[dict] = []
    # subtotal group → the row in the source sheet that prints that subtotal.
    # Render writes each =SUM into this row rather than matching label text,
    # which varies too much across associations to rely on.
    subtotal_rows: dict[str, int] = {}


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
    # Grand totals exactly as PRINTED in the report ("TOTAL REVENUES",
    # "TOTAL EXPENSES"). These are the only figures safe to reconcile against:
    # a report's section headings need not match the workbook's, but the grand
    # total covers the same dollars under either taxonomy.
    pdf_total_revenue: float | None = None
    pdf_total_expenses: float | None = None
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
    # subtotal group → source-sheet row printing that subtotal (see IngestResult).
    subtotal_rows: dict[str, int] = {}
