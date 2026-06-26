# app/services/budget/exceptions.py


class BudgetPipelineError(Exception):
    pass


class MissingInputFile(BudgetPipelineError):
    """A required input file was not provided."""
    pass


class UnmappedGLAccount(BudgetPipelineError):
    """The financial report contains a GL account not in the mapping table."""

    def __init__(self, accounts: list[str]):
        self.accounts = accounts
        super().__init__(f"Unmapped GL accounts: {', '.join(accounts)}")


class ValidationFailed(BudgetPipelineError):
    """One or more structural or arithmetic validation checks failed."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("Validation failed:\n" + "\n".join(f"  - {e}" for e in errors))


class IngestFailed(BudgetPipelineError):
    """AI extraction from the input files failed or returned incomplete data."""
    pass


class CrossCheckFailed(BudgetPipelineError):
    """Extracted GL lines don't reconcile against the PDF's printed section totals."""

    def __init__(self, mismatches: list[str]):
        self.mismatches = mismatches
        super().__init__("Cross-check failed:\n" + "\n".join(f"  - {m}" for m in mismatches))


class RenderFailed(BudgetPipelineError):
    """XLSX generation failed or produced formula errors."""
    pass
