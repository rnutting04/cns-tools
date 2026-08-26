# app/models/budget_layout_profile.py
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class BudgetLayoutProfile(Base):
    """
    A confirmed reading of one association workbook template.

    Keyed by `signature` — a structural fingerprint that excludes amounts and
    association names — so a layout confirmed once is reused automatically by
    every association whose workbook has the same shape, and by the same
    association next year. With ~200 associations that is what keeps
    confirmation from becoming 200 separate reviews.
    """

    __tablename__ = "budget_layout_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Structural fingerprint from layout.fingerprint(); the reuse key.
    signature = Column(String(32), nullable=False, unique=True, index=True)

    # The confirmed layout.
    sheet_title = Column(String(255), nullable=False)
    header_row = Column(Integer, nullable=False)
    label_col = Column(Integer, nullable=False)
    prior_col = Column(Integer, nullable=True)
    projected_col = Column(Integer, nullable=True)
    proposed_col = Column(Integer, nullable=True)
    notes_col = Column(Integer, nullable=True)
    reserve_sheet = Column(String(255), nullable=True)
    # {row -> section} plus the value-column roles, as detected or corrected.
    section_rows = Column(JSON, nullable=False, default=dict)
    value_cols = Column(JSON, nullable=False, default=list)

    # False while a human has not yet signed off. An unconfirmed profile is
    # never reused to skip review.
    confirmed = Column(Boolean, nullable=False, default=False, index=True)

    # Why review was requested, so the UI can explain itself.
    warnings = Column(JSON, nullable=True)

    # Provenance — which workbook first produced this shape.
    example_association = Column(String(255), nullable=True)
    example_filename = Column(String(255), nullable=True)
    # How many jobs have reused this profile; makes the payoff visible.
    use_count = Column(Integer, nullable=False, default=0)

    confirmed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    confirmer = relationship("User")
