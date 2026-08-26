# app/models/budget_job.py
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.letter_job import JobStatus


class BudgetJob(Base):
    __tablename__ = "budget_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    association_name = Column(String(255), nullable=False)
    budget_year = Column(Integer, nullable=False)

    # MinIO keys for the uploaded input files.
    financial_report_path = Column(String(500), nullable=False)
    financial_report_filename = Column(String(255), nullable=False)
    prior_budget_path = Column(String(500), nullable=False)
    prior_budget_filename = Column(String(255), nullable=False)

    # Set on completion.
    output_path = Column(String(500), nullable=True)
    review_flag_count = Column(Integer, nullable=True)

    # Updated between pipeline stages so the frontend can show progress.
    current_step = Column(String(50), nullable=True)

    # Set on failure.
    error_code = Column(String(50), nullable=True)
    error_detail = Column(JSON, nullable=True)

    # Layout review. When workbook structure detection is not confident and no
    # confirmed profile matches, the run parks here with
    # current_step == "awaiting_layout_review" and layout_review holding the
    # detected structure plus a preview for the reviewer. Confirming resumes it.
    layout_signature = Column(String(32), nullable=True, index=True)
    layout_review = Column(JSON, nullable=True)

    # Reuses the jobstatus enum already in the DB (create_type=False).
    status = Column(
        SAEnum(JobStatus, name="jobstatus", create_type=False),
        nullable=False,
        default=JobStatus.pending,
    )

    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    creator = relationship("User")
